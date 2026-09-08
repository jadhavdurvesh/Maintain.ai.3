"""
Turns the database's accumulated machine history into model features.
Sensor features are compact rolling summaries, not raw high-frequency data,
so the local RandomForest stays small and fast.
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
    "temperature_avg",
    "temperature_max",
    "vibration_avg",
    "vibration_max",
    "current_avg",
    "current_max",
    "load_avg",
    "load_max",
]

_CRITICALITY_SCORE = {"low": 0, "medium": 1, "high": 2}


def _sensor_features(db: Session, machine_id: int) -> list[float]:
    """Return compact summaries of the latest 30 sensor readings."""
    readings = (
        db.query(models.SensorReading)
        .filter_by(machine_id=machine_id)
        .order_by(models.SensorReading.recorded_at.desc())
        .limit(30)
        .all()
    )
    values = {"temperature": [], "vibration": [], "current": [], "load": []}
    for reading in readings:
        kind = (reading.reading_type or "").lower()
        if kind in values:
            values[kind].append(float(reading.value))

    features = []
    for kind in ("temperature", "vibration", "current", "load"):
        sample = values[kind]
        features.extend([
            sum(sample) / len(sample) if sample else 0.0,
            max(sample) if sample else 0.0,
        ])
    return features


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
        *_sensor_features(db, machine.id),
    ]


def build_training_data(db: Session):
    """One training row per active machine: features -> current health_score.
    Sensor columns use compact rolling summaries, keeping the model cheap to
    train and predict while allowing live sensor history to influence results.
    """
    machines = db.query(models.Machine).filter_by(archived=False).all()
    X, y, machine_ids = [], [], []
    for m in machines:
        X.append(machine_features(db, m))
        y.append(m.health_score)
        machine_ids.append(m.id)
    return X, y, machine_ids
