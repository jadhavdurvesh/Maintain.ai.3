from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models
from ..database import SessionLocal, get_db
from ..deps import CurrentUser, get_current_user
from .forecast_runs import MLForecastRun
from .forecasting import _call_ml_service, _interval_seconds, _model, _telemetry_is_fresh, serialize_run

router = APIRouter(prefix="", tags=["prediction-windows"])

WINDOWS = {
    "24h": {"seconds": 24 * 3600, "step_seconds": 3600, "steps": 24},
    "48h": {"seconds": 48 * 3600, "step_seconds": 3600, "steps": 48},
    "7d": {"seconds": 7 * 24 * 3600, "step_seconds": 6 * 3600, "steps": 28},
    "30d": {"seconds": 30 * 24 * 3600, "step_seconds": 24 * 3600, "steps": 30},
}
SUPPORTED_SIGNALS = {"temperature", "vibration", "current", "load", "humidity"}
SUPPORTED_MODELS = {"chronos-bolt-tiny", "timer"}


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
    return db.query(MLForecastRun).filter(MLForecastRun.machine_id == machine_id, MLForecastRun.reading_type == reading_type, MLForecastRun.model == model, MLForecastRun.forecast_window == window, MLForecastRun.status.in_(["completed", "running"])).order_by(MLForecastRun.created_at.desc()).first()


def _latest_telemetry(db, machine_id, reading_type):
    return db.query(models.SensorReading).filter_by(machine_id=machine_id, reading_type=reading_type).order_by(models.SensorReading.recorded_at.desc(), models.SensorReading.id.desc()).first()


def _run_window(db, machine, reading_type, window, model, trigger="automatic", force=False):
    spec = WINDOWS[window]
    latest = _latest_telemetry(db, machine.id, reading_type)
    if latest is None:
        return {"available": False, "window": window, "reason": "No telemetry available. Forecasting is paused until sensor telemetry exists."}
    fresh = _telemetry_is_fresh(latest.recorded_at)
    # Automatic windows require live telemetry. An explicit Model Lab run is a
    # historical replay and can use stored telemetry when the stream is idle.
    if not fresh and trigger != "manual":
        return {"available": False, "window": window, "reason": f"Telemetry is stale (last reading {latest.recorded_at.isoformat()}); automatic inference is paused."}
    previous = _latest_run(db, machine.id, reading_type, model, window)
    if previous and previous.status == "running" and not force:
        return {"available": False, "running": True, "window": window, "reason": "A forecast for this machine/window is already running.", "run": serialize_run(previous, reused=True)}
    if previous and not force:
        if previous.input_last_reading_id == latest.id:
            return {"available": True, "skipped": True, "window": window, "reason": "No new telemetry since the previous forecast.", "run": serialize_run(previous, reused=True)}
        if datetime.utcnow() - previous.created_at < timedelta(seconds=max(_interval_seconds(), spec["step_seconds"] // 2)):
            return {"available": True, "skipped": True, "window": window, "reason": "Forecast cadence has not elapsed yet.", "run": serialize_run(previous, reused=True)}
    rows = _window_rows(db, machine.id, reading_type, spec["seconds"], spec["step_seconds"])
    values, started_at, ended_at = _bucket_series(rows, spec["step_seconds"])
    if len(values) < 16:
        return {"available": False, "window": window, "reason": f"At least 16 time buckets are required for the {window} forecast; only {len(values)} are available."}
    run = MLForecastRun(organization_id=machine.organization_id, machine_id=machine.id, reading_type=reading_type, model=model, horizon=spec["steps"], forecast_window=window, step_seconds=spec["step_seconds"], input_first_reading_id=rows[0].id, input_last_reading_id=latest.id, input_started_at=started_at, input_ended_at=latest.recorded_at, input_reading_count=len(rows), trigger=trigger, status="running")
    db.add(run)
    try:
        db.commit()
        db.refresh(run)
    except IntegrityError:
        db.rollback()
        existing = db.query(MLForecastRun).filter_by(machine_id=machine.id, reading_type=reading_type, model=model, horizon=spec["steps"], input_last_reading_id=latest.id, forecast_window=window).first()
        if existing:
            return {"available": existing.status == "completed", "running": existing.status == "running", "window": window, "reason": "Forecast already reserved for this telemetry snapshot.", "run": serialize_run(existing, reused=True)}
        raise
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
    if model not in SUPPORTED_MODELS:
        raise HTTPException(400, "unsupported forecast model")
    result = {}
    for window in WINDOWS:
        run = db.query(MLForecastRun).filter(MLForecastRun.machine_id == machine_id, MLForecastRun.reading_type == reading_type, MLForecastRun.model == model, MLForecastRun.forecast_window == window, MLForecastRun.status == "completed").order_by(MLForecastRun.created_at.desc()).first()
        result[window] = serialize_run(run) if run else {"available": False, "window": window, "reason": "No forecast generated yet."}
        result[window]["step_seconds"] = WINDOWS[window]["step_seconds"]
        result[window]["steps"] = WINDOWS[window]["steps"]
    return {"machine_id": machine_id, "reading_type": reading_type, "model": model, "windows": result}


@router.get("/machines/{machine_id}/windows/run")
def run_forecast_window(machine_id: int, window: str = "24h", reading_type: str = "temperature", model: str = "chronos-bolt-tiny", current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if machine_id not in _visible_machine_ids(db, current):
        raise HTTPException(404, "machine not found")
    if window not in WINDOWS:
        raise HTTPException(400, "window must be one of 24h, 48h, 7d, 30d")
    if reading_type not in SUPPORTED_SIGNALS:
        raise HTTPException(400, "unsupported signal")
    if model not in SUPPORTED_MODELS:
        raise HTTPException(400, "unsupported forecast model")
    machine = db.query(models.Machine).filter_by(id=machine_id, archived=False).first()
    try:
        return _run_window(db, machine, reading_type, window, model, "manual", force=True)
    except Exception as exc:
        db.rollback()
        raise HTTPException(502, str(exc)) from exc


@router.get("/machines/{machine_id}/windows/compare")
def compare_forecast_window(machine_id: int, window: str = "24h", reading_type: str = "temperature", current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if machine_id not in _visible_machine_ids(db, current):
        raise HTTPException(404, "machine not found")
    if window not in WINDOWS:
        raise HTTPException(400, "window must be one of 24h, 48h, 7d, 30d")
    if reading_type not in SUPPORTED_SIGNALS:
        raise HTTPException(400, "unsupported signal")
    machine = db.query(models.Machine).filter_by(id=machine_id, archived=False).first()
    results = {}
    for model in ("chronos-bolt-tiny", "timer"):
        try:
            results[model] = _run_window(db, machine, reading_type, window, model, "comparison", force=False)
        except Exception as exc:
            db.rollback()
            results[model] = {"available": False, "window": window, "model": model, "reason": str(exc)}
    chronos = results.get("chronos-bolt-tiny", {})
    timer = results.get("timer", {})
    chronos_run = chronos.get("run", chronos)
    timer_run = timer.get("run", timer)
    return {"machine_id": machine_id, "reading_type": reading_type, "window": window, "models": results, "comparison": {"endpoint_delta": (timer_run.get("end_prediction") - chronos_run.get("end_prediction")) if timer_run.get("end_prediction") is not None and chronos_run.get("end_prediction") is not None else None, "same_direction": timer_run.get("trend") == chronos_run.get("trend") if timer_run.get("trend") and chronos_run.get("trend") else None}}


@router.get("/fleet/windows")
def fleet_forecast_windows(reading_type: str = "temperature", model: str = "chronos-bolt-tiny", current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    machine_ids = _visible_machine_ids(db, current)
    machines = {m.id: m for m in db.query(models.Machine).filter(models.Machine.id.in_(machine_ids)).all()}
    rows = []
    for machine_id, machine in machines.items():
        latest = _latest_telemetry(db, machine_id, reading_type)
        machine_row = {"machine_id": machine_id, "machine_name": machine.name, "category": machine.category, "telemetry_at": latest.recorded_at.isoformat() if latest else None, "windows": {}}
        for window in WINDOWS:
            run = db.query(MLForecastRun).filter(MLForecastRun.machine_id == machine_id, MLForecastRun.reading_type == reading_type, MLForecastRun.model == model, MLForecastRun.forecast_window == window, MLForecastRun.status == "completed").order_by(MLForecastRun.created_at.desc()).first()
            machine_row["windows"][window] = serialize_run(run) if run else {"available": False, "window": window, "reason": "No forecast generated yet."}
        rows.append(machine_row)
    return {"generated_at": datetime.utcnow().isoformat(), "reading_type": reading_type, "model": model, "windows": list(WINDOWS), "machines": rows}
