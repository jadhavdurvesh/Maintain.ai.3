"""Online machine-behaviour learning for the Lab branch.

This complements the existing Random Forest. It learns each machine's live
sensor baseline incrementally, without rebuilding a training dataset for every
reading. Welford statistics provide an online mean/variance and EWMA captures
short-term drift.

The first phase intentionally produces evidence/anomaly scores. Notification
policy and supervised model promotion stay separate until validated.
"""
import math
from datetime import datetime

from sqlalchemy.orm import Session

from .. import models

FEATURES = ("temperature", "vibration", "current", "load")
MODEL_VERSION = 1


def _safe_float(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _get_state(db: Session, machine_id: int, reading_type: str):
    return (
        db.query(models.MLBehaviourState)
        .filter_by(machine_id=machine_id, reading_type=reading_type)
        .first()
    )


def update_online_state(db: Session, machine: models.Machine, reading: models.SensorReading) -> dict:
    reading_type = (reading.reading_type or "").lower().strip()
    value = _safe_float(reading.value)

    if reading_type not in FEATURES or value is None:
        return {"available": False, "reason": "unsupported ML reading type"}

    state = _get_state(db, machine.id, reading_type)
    if state is None:
        state = models.MLBehaviourState(
            machine_id=machine.id,
            reading_type=reading_type,
            model_version=MODEL_VERSION,
        )
        db.add(state)
        db.flush()

    previous_mean = state.mean_value
    previous_ewma = state.ewma if state.sample_count else value

    # Welford online mean/variance update.
    n = state.sample_count + 1
    delta = value - state.mean_value
    mean = state.mean_value + (delta / n)
    delta2 = value - mean
    m2 = state.m2 + (delta * delta2)
    variance = m2 / (n - 1) if n > 1 else 0.0
    std = math.sqrt(max(variance, 0.0))

    # EWMA responds faster than the long-term baseline.
    alpha = 0.25
    ewma = value if state.sample_count == 0 else alpha * value + (1 - alpha) * state.ewma

    z_score = 0.0 if std < 1e-9 else abs(value - mean) / std
    anomaly_score = min(1.0, z_score / 6.0)
    trend_delta = abs(ewma - previous_ewma)

    state.sample_count = n
    state.mean_value = mean
    state.m2 = m2
    state.variance = variance
    state.ewma = ewma
    state.last_value = value
    state.last_anomaly_score = anomaly_score
    state.updated_at = datetime.utcnow()
    db.flush()

    # Avoid strong events during cold-start and require persistent evidence.
    persistent_change = (
        n >= 10
        and anomaly_score >= 0.35
        and (
            previous_mean == 0
            or abs(value - previous_mean) / max(abs(previous_mean), 1e-9) >= 0.05
            or trend_delta > max(std * 0.25, 1e-6)
        )
    )

    return {
        "available": True,
        "machine_id": machine.id,
        "reading_type": reading_type,
        "value": value,
        "baseline_mean": round(mean, 5),
        "baseline_std": round(std, 5),
        "ewma": round(ewma, 5),
        "z_score": round(z_score, 4),
        "anomaly_score": round(anomaly_score, 4),
        "persistent_change": persistent_change,
        "samples": n,
    }


def score_machine(db: Session, machine_id: int) -> dict:
    states = db.query(models.MLBehaviourState).filter_by(machine_id=machine_id).all()

    if not states:
        return {"available": False, "reason": "No online-learning state yet."}

    signals = []
    for state in states:
        signals.append({
            "reading_type": state.reading_type,
            "anomaly_score": round(state.last_anomaly_score, 4),
            "samples": state.sample_count,
            "ewma": round(state.ewma, 5),
            "mean": round(state.mean_value, 5),
            "std": round(math.sqrt(max(state.variance, 0.0)), 5),
        })

    signals.sort(key=lambda item: item["anomaly_score"], reverse=True)
    max_score = signals[0]["anomaly_score"] if signals else 0.0

    return {
        "available": True,
        "machine_id": machine_id,
        "behaviour_anomaly_score": round(max_score, 4),
        "severity": (
            "critical" if max_score >= 0.80
            else "high" if max_score >= 0.60
            else "warning" if max_score >= 0.35
            else "normal"
        ),
        "signals": signals,
    }
