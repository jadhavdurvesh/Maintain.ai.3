"""Readiness metrics for future calibrated failure-risk models.

This module reports whether the database contains enough complete point-in-time
outcomes for each requested horizon. It never turns sparse labels into a fake
probability or score.
"""
from sqlalchemy import func
from .. import models

HORIZONS = {
    "24h": 24 * 3600,
    "48h": 48 * 3600,
    "7d": 7 * 24 * 3600,
    "30d": 30 * 24 * 3600,
}


def risk_readiness(db, machine_ids=None):
    result = {}
    for name, seconds in HORIZONS.items():
        q = db.query(
            func.count(models.MLTrainingLabel.id),
            func.sum(func.cast(models.MLTrainingLabel.fault_within_horizon, db.bind.dialect.name == "postgresql" if False else None))
        )
        query = db.query(models.MLTrainingLabel).filter_by(horizon_seconds=seconds)
        if machine_ids is not None:
            query = query.filter(models.MLTrainingLabel.machine_id.in_(machine_ids))
        rows = query.all()
        complete = len(rows)
        positives = sum(1 for row in rows if row.fault_within_horizon or row.breakdown_work_order_within_horizon)
        result[name] = {
            "horizon_seconds": seconds,
            "complete_labels": complete,
            "positive_outcomes": positives,
            "negative_outcomes": complete - positives,
            "calibrated_probability_available": False,
        }
    return {
        "available": False,
        "status": "data_collection_and_validation",
        "message": "Future failure-risk probabilities remain disabled until sufficient, leakage-safe outcomes are collected and a horizon-specific model is validated.",
        "horizons": result,
    }


def fleet_intelligence(db, machine_ids=None):
    from .degradation import build_snapshot
    query = db.query(models.Machine).filter_by(archived=False)
    if machine_ids is not None:
        query = query.filter(models.Machine.id.in_(machine_ids))
    machines = query.order_by(models.Machine.id.asc()).all()
    fleet = []
    for machine in machines:
        snapshot = build_snapshot(db, machine.id)
        fleet.append({
            "machine_id": machine.id,
            "machine_name": machine.name,
            "category": machine.category,
            "health_score": machine.health_score,
            "status": machine.status.value if hasattr(machine.status, "value") else machine.status,
            "degradation_score": snapshot.get("degradation_score", 0),
            "trend_score": snapshot.get("trend_score", 0),
            "active_signal_count": snapshot.get("active_signal_count", 0),
            "evidence": snapshot.get("evidence", []),
        })
    fleet.sort(key=lambda x: x["degradation_score"], reverse=True)
    return {
        "machines": fleet,
        "count": len(fleet),
        "note": "Fleet ordering is by current degradation evidence for operational triage; it is not a model quality ranking or failure prediction.",
    }
