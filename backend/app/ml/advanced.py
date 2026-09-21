"""Compact temporal predictive-maintenance model for live Lab inference."""
import json
import math
from datetime import datetime, timedelta
from statistics import mean, pstdev

from sqlalchemy.orm import Session

from .. import models

MODEL_TYPE = "temporal_gbdt"
MODEL_VERSION = 1
SIGNALS = ("temperature", "vibration", "current", "load")


def _stats(rows):
    values = [float(r.value) for r in rows]
    if not values:
        return {"latest": 0.0, "mean": 0.0, "std": 0.0, "slope": 0.0, "ewma": 0.0, "delta": 0.0, "range": 0.0, "count": 0}
    latest = values[-1]
    avg = mean(values)
    std = pstdev(values) if len(values) > 1 else 0.0
    times = [r.recorded_at.timestamp() / 60.0 for r in rows]
    if len(values) > 1:
        t_mean = mean(times)
        denom = sum((t - t_mean) ** 2 for t in times)
        slope = sum((t - t_mean) * (v - avg) for t, v in zip(times, values)) / denom if denom > 1e-12 else 0.0
    else:
        slope = 0.0
    ewma = values[0]
    for value in values[1:]:
        ewma = 0.35 * value + 0.65 * ewma
    return {
        "latest": latest, "mean": avg, "std": std, "slope": slope,
        "ewma": ewma, "delta": latest - avg,
        "range": max(values) - min(values), "count": len(values),
    }


def build_feature_vector(db: Session, machine: models.Machine, as_of=None):
    cutoff = as_of or datetime.utcnow()
    window_start = cutoff - timedelta(hours=6)
    names, features = [], []

    for signal in SIGNALS:
        rows = (
            db.query(models.SensorReading)
            .filter(
                models.SensorReading.machine_id == machine.id,
                models.SensorReading.reading_type == signal,
                models.SensorReading.recorded_at <= cutoff,
                models.SensorReading.recorded_at >= window_start,
            )
            .order_by(models.SensorReading.recorded_at.asc())
            .limit(60)
            .all()
        )
        stats = _stats(rows)
        for suffix in ("latest", "mean", "std", "slope", "ewma", "delta", "range", "count"):
            names.append(f"{signal}_{suffix}")
            features.append(float(stats[suffix]))

    fault_count = db.query(models.FaultRecord).filter_by(machine_id=machine.id).count()
    unresolved = db.query(models.FaultRecord).filter_by(machine_id=machine.id, resolved_date=None).count()
    interval = float(machine.maintenance_interval_hours or 500.0)
    extras = [
        ("health_score", float(machine.health_score or 0)),
        ("operating_hours", float(machine.operating_hours or 0)),
        ("hours_since_maintenance", float(machine.operating_hours or 0) % interval),
        ("fault_count_total", float(fault_count)),
        ("unresolved_fault_count", float(unresolved)),
    ]
    for name, value in extras:
        names.append(name)
        features.append(value)
    return names, features


def _sigmoid(value):
    value = max(-40.0, min(40.0, value))
    return 1.0 / (1.0 + math.exp(-value))


def _tree_value(tree, features):
    node = 0
    while True:
        current = tree[node]
        feature = int(current["feature"])
        if feature < 0:
            return float(current["value"])
        node = int(current["left"] if features[feature] <= float(current["threshold"]) else current["right"])


def score_features(artifact, features):
    raw = float(artifact.get("base_logit", 0.0))
    learning_rate = float(artifact.get("learning_rate", 0.1))
    for tree in artifact.get("trees", []):
        raw += learning_rate * _tree_value(tree, features)
    return _sigmoid(raw)


def load_active_artifact(db: Session, organization_id: int):
    row = (
        db.query(models.MLAdvancedArtifact)
        .filter(
            models.MLAdvancedArtifact.organization_id == organization_id,
            models.MLAdvancedArtifact.active.is_(True),
        )
        .order_by(models.MLAdvancedArtifact.id.desc())
        .first()
    )
    if not row:
        return None
    try:
        return row, json.loads(bytes(row.artifact).decode("utf-8"))
    except Exception:
        return None


def model_status(db: Session, organization_id: int):
    loaded = load_active_artifact(db, organization_id)
    if not loaded:
        return {
            "available": False,
            "trained": False,
            "model_type": MODEL_TYPE,
            "reason": "No active advanced temporal model has been trained yet.",
        }
    row, artifact = loaded
    return {
        "available": True,
        "trained": True,
        "model_type": row.model_type,
        "model_version": row.model_version,
        "trained_at": row.trained_at.isoformat() if row.trained_at else None,
        "n_samples": row.n_samples,
        "n_positive": row.n_positive,
        "feature_count": len(artifact.get("feature_names", [])),
        "metrics": json.loads(row.metrics_json) if row.metrics_json else {},
    }


def predict_machine(db: Session, machine: models.Machine):
    loaded = load_active_artifact(db, machine.organization_id)
    names, features = build_feature_vector(db, machine)
    if not loaded:
        return {
            "available": False,
            "machine_id": machine.id,
            "machine_name": machine.name,
            "feature_count": len(features),
            "reason": "Advanced supervised model is not trained yet; live online behaviour learning is still active.",
        }

    row, artifact = loaded
    if artifact.get("feature_names") != names:
        return {
            "available": False,
            "machine_id": machine.id,
            "reason": "Model feature schema does not match the current feature engine.",
        }

    score = score_features(artifact, features)
    return {
        "available": True,
        "machine_id": machine.id,
        "machine_name": machine.name,
        "model_version": row.model_version,
        "failure_risk_score": round(score, 5),
        "risk_band": (
            "critical" if score >= 0.80
            else "high" if score >= 0.60
            else "watch" if score >= 0.35
            else "normal"
        ),
        "trained_at": row.trained_at.isoformat() if row.trained_at else None,
    }
