"""
Turns the database's own accumulated history into training features. This is
what makes the model 'trained on your data' rather than a fixed formula:
every fault logged and every maintenance job completed changes these numbers
for next time you retrain.
"""
from sqlalchemy.orm import Session

from .. import models

FEATURE_NAMES = [
    "operating_hours",
    "hours_since_maintenance",
    "maintenance_interval_hours",
    "criticality_score",
    "fault_count_total",
    "unresolved_fault_count",
    "completed_maintenance_count",
]

_CRITICALITY_SCORE = {"low": 0, "medium": 1, "high": 2}


def machine_features(db: Session, machine: models.Machine) -> list:
    interval = machine.maintenance_interval_hours or 500
    hours_since_maintenance = machine.operating_hours % interval

    fault_count = db.query(models.FaultRecord).filter_by(machine_id=machine.id).count()
    unresolved = (
        db.query(models.FaultRecord)
        .filter_by(machine_id=machine.id, resolved_date=None)
        .count()
    )
    completed_maint = (
        db.query(models.MaintenanceRecord)
        .filter_by(machine_id=machine.id, status=models.MaintenanceStatus.completed)
        .count()
    )
    criticality = machine.criticality.value if hasattr(machine.criticality, "value") else str(machine.criticality)

    return [
        machine.operating_hours,
        hours_since_maintenance,
        interval,
        _CRITICALITY_SCORE.get(criticality, 1),
        fault_count,
        unresolved,
        completed_maint,
    ]


def build_training_data(db: Session):
    """One training row per active machine: features -> current health_score.
    Small dataset by nature (one row per machine you own) — it grows in
    richness (fault counts, completed-maintenance counts) as you use the
    app, even before you add more machines."""
    machines = db.query(models.Machine).filter_by(archived=False).all()
    X, y, machine_ids = [], [], []
    for m in machines:
        X.append(machine_features(db, m))
        y.append(m.health_score)
        machine_ids.append(m.id)
    return X, y, machine_ids
