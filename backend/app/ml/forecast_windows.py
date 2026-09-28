from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..database import SessionLocal, get_db
from ..deps import CurrentUser, get_current_user
from .forecast_runs import MLForecastRun
from .forecasting import _call_ml_service, _interval_seconds, _model, serialize_run

router = APIRouter(prefix="", tags=["prediction-windows"])

WINDOWS = {
    "24h": {"seconds": 24 * 3600, "step_seconds": 3600, "steps": 24},
    "48h": {"seconds": 48 * 3600, "step_seconds": 3600, "steps": 48},
    "7d": {"seconds": 7 * 24 * 3600, "step_seconds": 6 * 3600, "steps": 28},
    "30d": {"seconds": 30 * 24 * 3600, "step_seconds": 24 * 3600, "steps": 30},
}
SUPPORTED_SIGNALS = {"temperature", "vibration", "current", "load", "humidity"}


def _visible_machine_ids(db: Session, current: CurrentUser):
    q = db.query(models.Machine.id).filter(models.Machine.organization_id == current.organization_id, models.Machine.archived.is_(False))
    if current.id is not None and current.role == models.UserRole.technician.value:
        q = q.join(models.UserMachineAssignment, models.UserMachineAssignment.machine_id == models.Machine.id).filter(models.UserMachineAssignment.user_id == current.id)
    return [row[0] for row in q.all()]


def _bucket_series(rows, step_seconds: int, max_points: int = 2048):
    if not rows:
        return [], None, None
    ordered = sorted(rows, key=lambda r: (r.recorded_at, r.id))
    buckets = {}
    for row in ordered:
        bucket = int(row.recorded_at.timestamp() // step_seconds) * step_seconds
        buckets.setdefault(bucket, []).append(float(row.value))
    points = [(bucket, sum(values) / len(values)) for bucket, values in sorted(buckets.items())]
    if len(points) > max_points:
        stride = (len(points) + max_points - 1) // max_points
        points = points[::stride]
    return [value for _, value in points], datetime.utcfromtimestamp(points[0][0]) if points else None, datetime.utcfromtimestamp(points[-1][0]) if points else None


def _window_rows(db: Session, machine_id: int, reading_type: str, window_seconds: int, step_seconds: int):
    context_seconds = max(window_seconds * 2, step_seconds * 64)
    cutoff = datetime.utcnow() - timedelta(seconds=context_seconds)
    return db.query(models.SensorReading).filter(models.SensorReading.machine_id == machine_id, models.SensorReading.reading_type == reading_type, models.SensorReading.recorded_at >= cutoff).order_by(models.SensorReading.recorded_at.asc(), models.SensorReading.id.asc()).limit(20000).all()


def _latest_run(db, machine_id, reading_type, model, window):
    return db.query(MLForecastRun).filter(MLForecastRun.machine_id == machine_id, MLForecastRun.reading_type == reading_type, MLForecastRun.model == model, MLForecastRun.forecast_window == window, MLForecastRun.status == "completed").order_by(MLForecastRun.created_at.desc()).first()


def _latest_telemetry(db, machine_id, reading_type):
    return db.query(models.SensorReading).filter_by(machine_id=machine_id, reading_type=reading_type).order_by(models.SensorReading.recorded_at.desc(), models.SensorReading.id.desc()).first()


def _run_window(db, machine, reading_type, window, model, trigger="automatic", force=False):
    spec = WINDOWS[window]
    latest = _latest_telemetry(db, machine.id, reading_type)
    if latest is None:
        return {"available": False, "window": window, "reason": "No telemetry available."}
    previous = _latest_run(db, machine.id, reading_type, model, window)
    if previous and not force:
        if previous.input_last_reading_id == latest.id:
            return {"available": True, "skipped": True, "reason": "No new telemetry since the previous forecast.", "run": serialize_run(previous, reused=True)}
        if datetime.utcnow() - previous.created_at < timedelta(seconds=max(_interval_seconds(), spec["step_seconds"] // 2)):
            return {"available": True, "skipped": True, "reason": "Forecast cadence has not elapsed yet.", "run": serialize_run(previous, reused=True)}
    rows = _window_rows(db, machine.id, reading_type, spec["seconds"], spec["step_seconds"])
    values, started_at, ended_at = _bucket_series(rows, spec["step_seconds"])
    if len(values) < 16:
        return {"available": False, "window": window, "reason": f"At least 16 time buckets are required for the {window} forecast; only {len(values)} are available."}
    run = MLForecastRun(organization_id=machine.organization_id, machine_id=machine.id, reading_type=reading_type, model=model, horizon=spec["steps"], forecast_window=window, step_seconds=spec["step_seconds"], input_first_reading_id=rows[0].id, input_last_reading_id=latest.id, input_started_at=started_at, input_ended_at=latest.recorded_at, input_reading_count=len(rows), trigger=trigger, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        result = _call_ml_service(values, spec["steps"], model)
        forecast = [float(value) for value in result.get("forecast", [])]
        baseline = values[-1]
        end = forecast[-1]
        run.forecast_json = json.dumps(forecast, separators=(",", ":"))
        run.next_prediction = forecast[0]
        run.end_prediction = end
        run.trend = "Stable" if abs(end - baseline) < 1e-6 else "Increasing" if end > baseline else "Decreasing"
        run.status = "completed"
        run.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(run)
        return serialize_run(run)
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)[:2000]
        run.updated_at = datetime.utcnow()
        db.commit()
        raise


def automatic_forecast_windows_for_reading(machine_id: int, reading_type: str):
    if os.getenv("ML_AUTO_FORECASTS", "true").strip().lower() not in {"1", "true", "yes", "on"} or reading_type not in SUPPORTED_SIGNALS:
        return None
    db = SessionLocal()
    try:
        machine = db.query(models.Machine).filter_by(id=machine_id, archived=False).first()
        if not machine:
            return None
        results = {}
        for window in WINDOWS:
            try:
                results[window] = _run_window(db, machine, reading_type, window, _model(), "automatic")
            except Exception as exc:
                db.rollback()
                results[window] = {"available": False, "window": window, "reason": str(exc)}
        return results
    finally:
        db.close()


@router.get("/machines/{machine_id}/windows")
def machine_forecast_windows(machine_id: int, reading_type: str = "temperature", model: str = "chronos-bolt-tiny", current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if machine_id not in _visible_machine_ids(db, current):
        raise HTTPException(404, "machine not found")
    if reading_type not in SUPPORTED_SIGNALS:
        raise HTTPException(400, "unsupported signal")
    result = {}
    for window in WINDOWS:
        run = _latest_run(db, machine_id, reading_type, model, window)
        result[window] = serialize_run(run) if run else {"available": False, "window": window, "reason": "No forecast generated yet."}
        result[window]["step_seconds"] = WINDOWS[window]["step_seconds"]
        result[window]["steps"] = WINDOWS[window]["steps"]
    return {"machine_id": machine_id, "reading_type": reading_type, "model": model, "windows": result}


@router.get("/fleet/windows")
def fleet_forecast_windows(reading_type: str = "temperature", model: str = "chronos-bolt-tiny", current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    machine_ids = _visible_machine_ids(db, current)
    machines = {m.id: m for m in db.query(models.Machine).filter(models.Machine.id.in_(machine_ids)).all()}
    rows = []
    for machine_id, machine in machines.items():
        latest = _latest_telemetry(db, machine_id, reading_type)
        machine_row = {"machine_id": machine_id, "machine_name": machine.name, "category": machine.category, "telemetry_at": latest.recorded_at.isoformat() if latest else None, "windows": {}}
        for window in WINDOWS:
            run = _latest_run(db, machine_id, reading_type, model, window)
            machine_row["windows"][window] = serialize_run(run) if run else {"available": False, "window": window, "reason": "No forecast generated yet."}
        rows.append(machine_row)
    return {"generated_at": datetime.utcnow().isoformat(), "reading_type": reading_type, "model": model, "windows": list(WINDOWS), "machines": rows}
