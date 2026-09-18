from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..ml import model as risk_model
from ..ml.online import score_machine
from ..ml.temporal import artifact_status as temporal_artifact_status
from ..ml.pretrained import pretrained_status, score_machine as score_pretrained_machine
from ..ml.forecasts import forecast_status as forecast_models_status, forecast_signal as chronos_forecast
from ..ml.timer import timer_status, forecast as timer_forecast
from ..ml.degradation import get_timeline
from ..ml.intelligence import process_telemetry
from ..ml.risk_horizons import risk_readiness, fleet_intelligence
from .. import models

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/model-status")
def get_model_status(db: Session = Depends(get_db)):
    return risk_model.model_status(db)


@router.post("/train")
def train_model(db: Session = Depends(get_db)):
    return risk_model.train(db)


@router.get("/risk-predictions")
def get_risk_predictions(db: Session = Depends(get_db)):
    # Prediction requests are automatic-safe: the model layer may train or
    # refresh a compatible batch model when its automatic policy says it is due.
    return risk_model.predict_risk(db)


@router.get("/temporal-model-status")
def get_temporal_model_status():
    """Return the bootstrap temporal model artifact and calibration status."""
    return temporal_artifact_status()


@router.get("/pretrained-model-status")
def get_pretrained_model_status():
    """Return optional pretrained zero-shot model availability."""
    return pretrained_status()


@router.get("/machines/{machine_id}/pretrained-anomaly")
def get_pretrained_anomaly(machine_id: int, db: Session = Depends(get_db)):
    """Run optional pretrained anomaly inference without training or calibration."""
    if db.get(models.Machine, machine_id) is None:
        raise HTTPException(404, "machine not found")
    return score_pretrained_machine(db, machine_id)


@router.get("/machines/{machine_id}/intelligence")
def get_machine_intelligence(machine_id: int, db: Session = Depends(get_db)):
    """Combine online behavioural evidence with optional pretrained anomaly evidence."""
    if db.get(models.Machine, machine_id) is None:
        raise HTTPException(404, "machine not found")
    behaviour = score_machine(db, machine_id)
    pretrained = score_pretrained_machine(db, machine_id)
    return {
        "machine_id": machine_id,
        "online_behaviour": behaviour,
        "pretrained_anomaly": pretrained,
        "failure_probability": None,
        "failure_probability_status": "not_calibrated",
    }


@router.get("/machines/{machine_id}/behaviour")
def get_machine_behaviour(machine_id: int, db: Session = Depends(get_db)):
    """Return the Lab online learner's current behavioural evidence."""
    if db.get(models.Machine, machine_id) is None:
        raise HTTPException(404, "machine not found")
    return score_machine(db, machine_id)


@router.get("/live-behaviour")
def get_live_behaviour(db: Session = Depends(get_db)):
    """Return online behavioural state for every active machine.

    This endpoint is intentionally lightweight and uses the same online model
    updated by every sensor reading, so the frontend can poll it for a live
    monitoring view without loading scikit-learn.
    """
    machines = (
        db.query(models.Machine)
        .filter_by(archived=False)
        .order_by(models.Machine.id.asc())
        .all()
    )
    results = []
    for machine in machines:
        behaviour = score_machine(db, machine.id)
        results.append({
            "machine_id": machine.id,
            "machine_name": machine.name,
            "health_score": machine.health_score,
            "status": machine.status.value if hasattr(machine.status, "value") else machine.status,
            "behaviour": behaviour,
        })
    return {"machines": results}


@router.get("/machines/{machine_id}/degradation")
def get_machine_degradation(machine_id: int, limit: int = 48, db: Session = Depends(get_db)):
    """Return the explainable online degradation timeline."""
    if db.get(models.Machine, machine_id) is None:
        raise HTTPException(404, "machine not found")
    return get_timeline(db, machine_id, limit)


@router.get("/fleet-intelligence")
def get_fleet_intelligence(db: Session = Depends(get_db)):
    """Return current degradation evidence for the active fleet."""
    return fleet_intelligence(db)


@router.get("/risk-readiness")
def get_risk_readiness(db: Session = Depends(get_db)):
    """Return future-risk label readiness without exposing uncalibrated probabilities."""
    return risk_readiness(db)


@router.get("/forecast-model-status")
def get_forecast_model_status():
    return {"chronos_2": forecast_models_status(), "timer": timer_status()}


@router.get("/machines/{machine_id}/forecast")
def get_machine_forecast(machine_id: int, reading_type: str = "temperature", model: str = "chronos2", horizon: int = 12, db: Session = Depends(get_db)):
    machine = db.get(models.Machine, machine_id)
    if not machine:
        raise HTTPException(404, "machine not found")
    if horizon < 1 or horizon > 96:
        raise HTTPException(400, "horizon must be between 1 and 96")
    rows = (
        db.query(models.SensorReading)
        .filter_by(machine_id=machine_id, reading_type=reading_type)
        .order_by(models.SensorReading.recorded_at.desc(), models.SensorReading.id.desc())
        .limit(2880)
        .all()
    )
    values = [float(r.value) for r in reversed(rows)]
    if model.lower() in {"timer", "timer-84m"}:
        return {"machine_id": machine_id, "reading_type": reading_type, **timer_forecast(values, horizon)}
    return {"machine_id": machine_id, "reading_type": reading_type, **chronos_forecast(values, horizon)}
