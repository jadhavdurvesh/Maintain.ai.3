"""Online machine-behaviour learning for the Lab branch.

This complements the existing Random Forest. It learns each machine's live
sensor baseline incrementally, without rebuilding a training dataset for every
reading. Welford statistics provide an online mean/variance and EWMA captures
short-term drift.

The Lab layer also combines simultaneous sensor deviations so a machine can
surface a multi-sensor behavioural change rather than treating every signal in
isolation.
"""
import math
from datetime import datetime

from sqlalchemy.orm import Session

from .. import models

FEATURES = ("temperature", "vibration", "current", "load")
MODEL_VERSION = 2
ACTIVE_THRESHOLD = 0.35


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
    previous_std = math.sqrt(max(state.variance, 0.0))
    sample_count_before = state.sample_count

    # Score against the established baseline BEFORE incorporating this sample.
    # This prevents a sudden outlier from diluting its own anomaly score.
    z_score = 0.0 if sample_count_before < 3 or previous_std < 1e-9 else abs(value - previous_mean) / previous_std
    anomaly_score = min(1.0, z_score / 6.0)

    # Welford online mean/variance update.
    n = sample_count_before + 1
    delta = value - state.mean_value
    mean = state.mean_value + (delta / n)
    delta2 = value - mean
    m2 = state.m2 + (delta * delta2)
    variance = m2 / (n - 1) if n > 1 else 0.0
    std = math.sqrt(max(variance, 0.0))

    # EWMA responds faster than the long-term baseline.
    alpha = 0.25
    ewma = value if sample_count_before == 0 else alpha * value + (1 - alpha) * state.ewma
    trend_delta = abs(ewma - previous_ewma)

    state.sample_count = n
    state.model_version = MODEL_VERSION
    state.mean_value = mean
    state.m2 = m2
    state.variance = variance
    state.ewma = ewma
    state.last_value = value
    state.last_anomaly_score = anomaly_score
    state.updated_at = datetime.utcnow()
    db.flush()

    # Cold-start protection plus persistence prevents one noisy sample from
    # creating a strong behavioural event.
    persistent_change = (
        n >= 10
        and anomaly_score >= ACTIVE_THRESHOLD
        and (
            previous_mean == 0
            or abs(value - previous_mean) / max(abs(previous_mean), 1e-9) >= 0.05
            or trend_delta > max(previous_std * 0.25, 1e-6)
        )
    )

    return {
        "available": True,
        "machine_id": machine.id,
        "reading_type": reading_type,
        "value": value,
        "baseline_mean": round(previous_mean, 5),
        "baseline_std": round(previous_std, 5),
        "learned_mean": round(mean, 5),
        "learned_std": round(std, 5),
        "ewma": round(ewma, 5),
        "z_score": round(z_score, 4),
        "anomaly_score": round(anomaly_score, 4),
        "persistent_change": persistent_change,
        "samples": n,
    }


def _signal_direction(state: models.MLBehaviourState) -> int:
    """Return the learned short-term direction: +1, -1, or 0."""
    std = math.sqrt(max(state.variance, 0.0))
    if std < 1e-9:
        return 0
    drift = (state.ewma - state.mean_value) / std
    if abs(drift) < 0.20:
        return 0
    return 1 if drift > 0 else -1


def score_machine(db: Session, machine_id: int) -> dict:
    states = (
        db.query(models.MLBehaviourState)
        .filter_by(machine_id=machine_id)
        .order_by(models.MLBehaviourState.reading_type.asc())
        .all()
    )
    if not states:
        return {"available": False, "reason": "No online-learning state yet."}

    signals = []
    active_states = []
    for state in states:
        signal = {
            "reading_type": state.reading_type,
            "anomaly_score": round(state.last_anomaly_score, 4),
            "active": state.last_anomaly_score >= ACTIVE_THRESHOLD and state.sample_count >= 10,
            "samples": state.sample_count,
            "last_value": round(state.last_value, 5),
            "ewma": round(state.ewma, 5),
            "mean": round(state.mean_value, 5),
            "std": round(math.sqrt(max(state.variance, 0.0)), 5),
            "direction": _signal_direction(state),
        }
        signals.append(signal)
        if signal["active"]:
            active_states.append((state, signal))

    signals.sort(key=lambda item: item["anomaly_score"], reverse=True)
    max_score = signals[0]["anomaly_score"] if signals else 0.0

    # Multi-sensor correlation is deliberately evidence-based rather than a
    # probability. Two or more active signals moving together strengthen the
    # machine-level signal. Opposing directions do not get the same boost.
    active_count = len(active_states)
    directions = [signal["direction"] for _, signal in active_states if signal["direction"] != 0]
    if directions:
        dominant = 1 if sum(directions) >= 0 else -1
        agreement = sum(1 for direction in directions if direction == dominant) / len(directions)
    else:
        agreement = 0.0

    coincidence_boost = min(0.50, max(0, active_count - 1) * 0.15)
    direction_boost = 0.05 * agreement if active_count >= 2 else 0.0
    correlation_score = min(1.0, max_score * (1.0 + coincidence_boost) + direction_boost)
    correlated = active_count >= 2 and agreement >= 0.50

    correlation_severity = (
        "critical" if correlation_score >= 0.80
        else "high" if correlation_score >= 0.60
        else "warning" if correlation_score >= ACTIVE_THRESHOLD
        else "normal"
    )

    evidence = [
        {
            "reading_type": signal["reading_type"],
            "anomaly_score": signal["anomaly_score"],
            "direction": signal["direction"],
            "ewma": signal["ewma"],
            "baseline": signal["mean"],
        }
        for _, signal in active_states
    ]

    return {
        "available": True,
        "machine_id": machine_id,
        "behaviour_anomaly_score": round(max_score, 4),
        "severity": (
            "critical" if max_score >= 0.80
            else "high" if max_score >= 0.60
            else "warning" if max_score >= ACTIVE_THRESHOLD
            else "normal"
        ),
        "multi_sensor": {
            "correlated": correlated,
            "active_signals": active_count,
            "direction_agreement": round(agreement, 4),
            "correlation_score": round(correlation_score, 4),
            "severity": correlation_severity,
            "evidence": evidence,
        },
        "signals": signals,
    }
