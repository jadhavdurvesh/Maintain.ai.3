"""
The local predictive model — deliberately small and cheap to run:
RandomForestRegressor with 40 shallow trees. The saved model file is
typically well under 100KB and predicts in milliseconds on a single CPU
core, unlike the Gemini path (needs internet + an API key) or an LLM
(needs real RAM/GPU). It's the third leg of the AI Assistant's design:

  1. Offline rule engine   — static knowledge base, works with zero data
  2. Gemini (optional)     — cloud LLM, needs a key + internet
  3. This local model      — trains on YOUR OWN accumulated machine data;
                             improves as you log faults and complete
                             maintenance, entirely on-device

It predicts each machine's health score from its operational stress
indicators (hours run, faults logged, maintenance completed, criticality).
Comparing the prediction to the machine's *actual* health score is what
flags risk: a machine doing much worse than its usage pattern would
suggest is the one worth a closer look.
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


def train(db: Session) -> dict:
    X, y, machine_ids = build_training_data(db)

    if len(X) < MIN_TRAINING_SAMPLES:
        return {
            "trained": False,
            "reason": f"Only {len(X)} machine(s) on record — need at least {MIN_TRAINING_SAMPLES} "
                      f"for a model that means anything. Add more machines or accumulate more "
                      f"fault/maintenance history, then retrain.",
            "n_samples": len(X),
        }

    model = RandomForestRegressor(n_estimators=40, max_depth=4, random_state=42, min_samples_leaf=1)
    model.fit(X, y)

    # In-sample fit quality — with this few rows it's a sanity check, not a
    # real generalization measure. Said plainly in the response, not hidden.
    in_sample_r2 = model.score(X, y)

    joblib.dump({"model": model, "trained_at": datetime.utcnow().isoformat(), "n_samples": len(X)}, MODEL_PATH)

    importances = sorted(
        zip(FEATURE_NAMES, model.feature_importances_.tolist()),
        key=lambda p: p[1], reverse=True,
    )

    return {
        "trained": True,
        "n_samples": len(X),
        "in_sample_r2": round(in_sample_r2, 3),
        "feature_importances": [{"feature": f, "importance": round(v, 3)} for f, v in importances],
    }


def _load():
    if not os.path.exists(MODEL_PATH):
        return None
    try:
        return joblib.load(MODEL_PATH)
    except Exception:
        return None


def model_status() -> dict:
    saved = _load()
    if not saved:
        return {"trained": False, "reason": "Model hasn't been trained yet."}
    return {"trained": True, "trained_at": saved["trained_at"], "n_samples": saved["n_samples"]}


def predict_risk(db: Session) -> dict:
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
            reason = "Health is declining faster than its usage pattern would predict."
        elif residual > 10:
            reason = "Tracking better than expected for its usage pattern."
        else:
            reason = "Tracking as expected for its usage pattern."

        predictions.append({
            "machine_id": m.id,
            "machine_name": m.name,
            "actual_health_score": m.health_score,
            "predicted_health_score": round(predicted, 1),
            "risk_level": risk,
            "reason": reason,
        })

    predictions.sort(key=lambda p: {"high": 0, "medium": 1, "low": 2}[p["risk_level"]])
    return {"available": True, "trained_at": saved["trained_at"], "n_samples": saved["n_samples"], "predictions": predictions}
