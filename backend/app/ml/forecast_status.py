from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import CurrentUser, get_current_user
from .forecast_runs import MLForecastRun, serialize_run
from .forecasting import _interval_seconds, _telemetry_is_fresh

router = APIRouter(prefix="/api/predictions", tags=["prediction-status"])


def _visible_machine_ids(db: Session, current: CurrentUser):
    q = db.query(models.Machine.id).filter(models.Machine.organization_id == current.organization_id, models.Machine.archived.is_(False))
    if current.id is not None and current.role == models.UserRole.technician.value:
        q = q.join(models.UserMachineAssignment, models.UserMachineAssignment.machine_id == models.Machine.id).filter(models.UserMachineAssignment.user_id == current.id)
    return [row[0] for row in q.all()]


@router.get("/machines/{machine_id}/status")
def machine_forecast_status(machine_id: int, reading_type: str = "temperature", model: str = "chronos-bolt-tiny", horizon: int = 12, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if machine_id not in set(_visible_machine_ids(db, current)):
        raise HTTPException(404, "machine not found")
    latest = db.query(models.SensorReading).filter_by(machine_id=machine_id, reading_type=reading_type).order_by(models.SensorReading.recorded_at.desc(), models.SensorReading.id.desc()).first()
    latest_run = db.query(MLForecastRun).filter_by(machine_id=machine_id, reading_type=reading_type, model=model, horizon=horizon).filter(MLForecastRun.status == "completed").order_by(MLForecastRun.created_at.desc()).first()
    fresh = bool(latest and _telemetry_is_fresh(latest.recorded_at))
    return {"machine_id": machine_id, "reading_type": reading_type, "model": model, "horizon": horizon, "telemetry_active": fresh, "latest_telemetry_at": latest.recorded_at.isoformat() if latest else None, "latest_telemetry_id": latest.id if latest else None, "latest_value": float(latest.value) if latest else None, "sample_count": db.query(models.SensorReading.id).filter_by(machine_id=machine_id, reading_type=reading_type).count(), "interval_seconds": _interval_seconds(), "minimum_samples": 32, "latest_run": serialize_run(latest_run) if latest_run else None}


@router.get("/machines/{machine_id}/history")
def machine_forecast_history(machine_id: int, reading_type: str = "temperature", model: str = "chronos-bolt-tiny", horizon: int | None = None, forecast_window: str | None = None, limit: int = 50, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if machine_id not in set(_visible_machine_ids(db, current)):
        raise HTTPException(404, "machine not found")
    limit = max(1, min(int(limit), 200))
    query = db.query(MLForecastRun).filter(MLForecastRun.machine_id == machine_id, MLForecastRun.reading_type == reading_type, MLForecastRun.model == model)
    if horizon is not None:
        query = query.filter(MLForecastRun.horizon == horizon)
    if forecast_window:
        query = query.filter(MLForecastRun.forecast_window == forecast_window)
    runs = query.order_by(MLForecastRun.created_at.desc()).limit(limit).all()
    return {"machine_id": machine_id, "reading_type": reading_type, "model": model, "horizon": horizon, "forecast_window": forecast_window, "runs": [serialize_run(run) for run in runs], "count": len(runs), "generated_at": datetime.utcnow().isoformat()}
