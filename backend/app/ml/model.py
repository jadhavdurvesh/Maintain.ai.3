"""
The local predictive model — deliberately small and cheap to run:
RandomForestRegressor with 40 shallow trees. It predicts in milliseconds on
CPU and now uses compact rolling sensor summaries alongside the existing
maintenance/fault features.

The model is intentionally separate from the transparent live-health
adjustment in devices.py. The live adjustment keeps the visible machine
health responsive immediately; this RandomForest adds learned predictive
risk when its training data is retrained.
"""
import os
from datetime import datetime

import joblib
from sklearn.ensemble import RandomForestRegressor
from sqlalchemy.orm import Session

from .. import models
from .features import build_training_data, machine_features, FEATURE_NAMES

MODEL_PATH = os.getenv("MODEL_PATH", "./risk_model.joblib")
MIN_TRAINING_SAMPLES = 4
MODEL_VERSION = 2


def train(db: Session) -> dict:
    X, y, machine_ids = build_training_data(db)

    if len(X) < MIN_TRAINING_SAMPLES:
        return {
            "trained": False,
            "reason": f"Only {len(X)} machine(s) on record — need at least {MIN_TRAINING_SAMPLES} "
                      f"for a model that means anything. Add more machines or accumulate more "
                      f"fault, maintenance, and sensor history, then retrain.",
            "n_samples": len(X),
        }

    model = RandomForestRegressor(
        n_estimators=40,
        max_depth=4,
        random_state=42,
        min_samples_leaf=1,
        n_jobs=1,
    )
    model.fit(X, y)

    # With a small machine-level dataset this is a sanity check, not a real
    # generalization metric.
    in_sample_r2 = model.score(X, y)

    bundle = {
        "model": model,
        "trained_at": datetime.utcnow().isoformat(),
        "n_samples": len(X),
        "model_version": MODEL_VERSION,
        "feature_names": FEATURE_NAMES,
    }
    joblib.dump(bundle, MODEL_PATH)

    importances = sorted(
        zip(FEATURE_NAMES, model.feature_importances_.tolist()),
        key=lambda p: p[1], reverse=True,
    )

    return {
        "trained": True,
        "n_samples": len(X),
        "in_sample_r2": round(in_sample_r2, 3),
        "model_version": MODEL_VERSION,
        "sensor_aware": True,
        "feature_importances": [
            {"feature": f, "importance": round(v, 3)} for f, v in importances
        ],
    }


def _load():
    if not os.path.exists(MODEL_PATH):
        return None
    try:
        return joblib.load(MODEL_PATH)
    except Exception:
        return None


def _is_compatible(saved: dict) -> bool:
    return (
        isinstance(saved, dict)
        and saved.get("model_version") == MODEL_VERSION
        and saved.get("feature_names") == FEATURE_NAMES
    )


def model_status() -> dict:
    saved = _load()
    if not saved:
        return {"trained": False, "reason": "Model hasn't been trained yet."}
    if not _is_compatible(saved):
        return {
            "trained": False,
            "reason": "A previous model uses the older feature set — retrain to enable sensor-aware predictions.",
            "sensor_aware": True,
        }
    return {
        "trained": True,
        "trained_at": saved["trained_at"],
        "n_samples": saved["n_samples"],
        "model_version": MODEL_VERSION,
        "sensor_aware": True,
    }


def predict_risk(db: Session) -> dict:
    saved = _load()

    # A model created before sensor-aware features cannot accept the new
    # feature vector. Retrain once automatically so the live system does not
    # fail just because an older local model file is still present.
    if saved and not _is_compatible(saved):
        result = train(db)
        if not result.get("trained"):
            return {"available": False, **result}
        saved = _load()

    if not saved:
        return {"available": False, "reason": "Model hasn't been trained yet — use the Retrain button."}

    model = saved["model"]
    machines = db.query(models.Machine).filter_by(archived=False).all()
    if not machines:
        return {"available": False, "reason": "No active machines to predict for."}

    predictions = []
    for m in machines:
        features = machine_features(db, m)
        predicted = float(model.predict([features])[0])
        residual = m.health_score - predicted  # negative = doing worse than expected

        if m.health_score < 40 or residual < -20:
            risk = "high"
        elif m.health_score < 70 or residual < -10:
            risk = "medium"
        else:
            risk = "low"

        if residual < -10:
            reason = "Health is declining faster than its operating, maintenance, fault, and sensor pattern would predict."
        elif residual > 10:
            reason = "Tracking better than expected for its operating, maintenance, fault, and sensor pattern."
        else:
            reason = "Tracking as expected for its operating, maintenance, fault, and sensor pattern."

        predictions.append({
            "machine_id": m.id,
            "machine_name": m.name,
            "actual_health_score": m.health_score,
            "predicted_health_score": round(max(0.0, min(100.0, predicted)), 1),
            "risk_level": risk,
            "reason": reason,
        })

    predictions.sort(key=lambda p: {"high": 0, "medium": 1, "low": 2}[p["risk_level"]])
    return {
        "available": True,
        "trained_at": saved["trained_at"],
        "n_samples": saved["n_samples"],
        "model_version": MODEL_VERSION,
        "sensor_aware": True,
        "predictions": predictions,
    }
