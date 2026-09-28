from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models
from ..database import SessionLocal, get_db
from ..deps import CurrentUser, get_current_user
from .forecast_runs import MLForecastRun

router = APIRouter(prefix="/api/predictions", tags=["predictions"])

DEFAULT_MODEL = "chronos-bolt-tiny"
DEFAULT_INTERVAL_SECONDS = 300
MIN_SAMPLES = 32
CONTEXT_SAMPLES = 128
SUPPORTED_MODELS = {"chronos-bolt-tiny", "timer"}
SUPPORTED_SIGNALS = {"temperature", "vibration", "current", "load", "humidity"}


def _truthy(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _interval_seconds() -> int:
    try:
        return max(60, int(os.getenv("ML_FORECAST_INTERVAL_SECONDS", str(DEFAULT_INTERVAL_SECONDS))))
    except ValueError:
        return DEFAULT_INTERVAL_SECONDS


def _telemetry_is_fresh(recorded_at: datetime | None) -> bool:
    if recorded_at is None:
        return False
    return (datetime.utcnow() - recorded_at).total_seconds() <= max(_interval_seconds() * 3, 900)


def _model() -> str:
    value = os.getenv("ML_FORECAST_MODEL", DEFAULT_MODEL).strip().lower()
    return value if value in SUPPORTED_MODELS else DEFAULT_MODEL


def _signals() -> set[str]:
    raw = os.getenv("ML_AUTO_FORECAST_SIGNALS", ",".join(sorted(SUPPORTED_SIGNALS)))
    return {item.strip().lower() for item in raw.split(",") if item.strip()}.intersection(SUPPORTED_SIGNALS)


def _service_url() -> str:
    return os.getenv("MAINTAIN_ML_SERVICE_URL", "https://maintain-ai-ml.onrender.com").rstrip("/")


def _call_ml_service(values: list[float], horizon: int, model: str) -> dict:
    if model not in SUPPORTED_MODELS:
        raise RuntimeError(f"Unsupported forecast model: {model}")
    model_id = "amazon/chronos-bolt-tiny" if model == "chronos-bolt-tiny" else "timer"
    body = json.dumps({"model": model_id, "values": values[-CONTEXT_SAMPLES:], "horizon": horizon}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("MAINTAIN_ML_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(f"{_service_url()}/v1/forecast", data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=float(os.getenv("ML_FORECAST_TIMEOUT_SECONDS", "90"))) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ML service HTTP {exc.code}: {detail[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"ML service unavailable: {exc.reason}") from exc
    if not result.get("available"):
        raise RuntimeError(result.get("reason") or f"{model} did not return a forecast")
    forecast = [float(value) for value in result.get("forecast", [])]
    if not forecast:
        raise RuntimeError("ML service returned an empty forecast")
    return result


def _scoped_machine(db: Session, machine_id: int, current: CurrentUser):
    machine = db.query(models.Machine).filter(models.Machine.id == machine_id, models.Machine.organization_id == current.organization_id, models.Machine.archived.is_(False)).first()
    if not machine:
        raise HTTPException(404, "machine not found")
    if current.id is not None and current.role == models.UserRole.technician.value:
        assigned = db.query(models.UserMachineAssignment).filter_by(user_id=current.id, machine_id=machine_id).first()
        if not assigned:
            raise HTTPException(404, "machine not assigned to this worker")
    return machine


def _recent_rows(db: Session, machine_id: int, reading_type: str, limit: int = CONTEXT_SAMPLES):
    return db.query(models.SensorReading).filter_by(machine_id=machine_id, reading_type=reading_type).order_by(models.SensorReading.recorded_at.desc(), models.SensorReading.id.desc()).limit(limit).all()


def _existing_input(db: Session, machine_id: int, reading_type: str, model: str, horizon: int, last_id: int):
    return db.query(MLForecastRun).filter_by(machine_id=machine_id, reading_type=reading_type, model=model, horizon=horizon, input_last_reading_id=last_id).first()


def _new_run(db: Session, machine: models.Machine, reading_type: str, model: str, horizon: int, rows, trigger: str):
    ordered = list(reversed(rows))
    run = MLForecastRun(organization_id=machine.organization_id, machine_id=machine.id, reading_type=reading_type, model=model, horizon=horizon, input_first_reading_id=ordered[0].id, input_last_reading_id=ordered[-1].id, input_started_at=ordered[0].recorded_at, input_ended_at=ordered[-1].recorded_at, input_reading_count=len(ordered), trigger=trigger, status="running")
    db.add(run)
    try:
        db.commit()
        db.refresh(run)
        return run
    except IntegrityError:
        db.rollback()
        return _existing_input(db, machine.id, reading_type, model, horizon, ordered[-1].id)


def _finish_run(db: Session, run: MLForecastRun, result: dict):
    forecast = [float(value) for value in result.get("forecast", [])]
    latest = float(db.query(models.SensorReading.value).filter_by(id=run.input_last_reading_id).scalar())
    end = forecast[-1]
    delta = end - latest
    trend = "Stable" if abs(delta) < 1e-6 else "Increasing" if delta > 0 else "Decreasing"
    run.forecast_json = json.dumps(forecast, separators=(",", ":"))
    run.next_prediction = forecast[0]
    run.end_prediction = end
    run.trend = trend
    run.status = "completed"
    run.error_message = None
    run.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(run)
    return run


def _fail_run(db: Session, run: MLForecastRun, exc: Exception):
    run.status = "failed"
    run.error_message = str(exc)[:2000]
    run.updated_at = datetime.utcnow()
    db.commit()
    return run


def _run_forecast(db: Session, machine: models.Machine, reading_type: str, model: str, horizon: int, trigger: str, *, force: bool = False):
    if model not in SUPPORTED_MODELS:
        raise HTTPException(400, f"unsupported forecast model: {model}")
    if reading_type not in SUPPORTED_SIGNALS:
        raise HTTPException(400, f"unsupported signal: {reading_type}")
    if horizon < 1 or horizon > 64:
        raise HTTPException(400, "horizon must be between 1 and 64")
    rows = _recent_rows(db, machine.id, reading_type)
    if not rows:
        return {"available": False, "machine_id": machine.id, "reading_type": reading_type, "model": model, "horizon": horizon, "reason": "No telemetry available. Forecasting is paused until a fresh sensor reading arrives."}
    latest = rows[0]
    if not _telemetry_is_fresh(latest.recorded_at):
        return {"available": False, "machine_id": machine.id, "reading_type": reading_type, "model": model, "horizon": horizon, "reason": f"Telemetry is stale (last reading {latest.recorded_at.isoformat()}); no ML inference was started."}
    if len(rows) < MIN_SAMPLES:
        return {"available": False, "machine_id": machine.id, "reading_type": reading_type, "model": model, "horizon": horizon, "reason": f"At least {MIN_SAMPLES} {reading_type} samples are required; only {len(rows)} are available."}
    existing = _existing_input(db, machine.id, reading_type, model, horizon, latest.id)
    if existing and existing.status in {"completed", "running"}:
        return serialize_run(existing, reused=True)
    if not force:
        last = db.query(MLForecastRun).filter(MLForecastRun.machine_id == machine.id, MLForecastRun.reading_type == reading_type, MLForecastRun.model == model, MLForecastRun.horizon == horizon, MLForecastRun.status == "completed").order_by(MLForecastRun.created_at.desc()).first()
        if last and datetime.utcnow() - last.created_at < timedelta(seconds=_interval_seconds()):
            return {"available": True, "skipped": True, "reason": "Forecast cadence has not elapsed; waiting for more telemetry.", "next_eligible_at": (last.created_at + timedelta(seconds=_interval_seconds())).isoformat(), "run": serialize_run(last)}
    run = _new_run(db, machine, reading_type, model, horizon, rows, trigger)
    if run is None:
        return {"available": False, "reason": "Forecast reservation could not be created."}
    if run.status == "completed":
        return serialize_run(run, reused=True)
    values = [float(row.value) for row in reversed(rows)]
    try:
        result = _call_ml_service(values, horizon, model)
        return serialize_run(_finish_run(db, run, result))
    except Exception as exc:
        _fail_run(db, run, exc)
        if trigger == "manual":
            raise HTTPException(502, str(exc)) from exc
        return serialize_run(run)


def serialize_run(run: MLForecastRun, reused: bool = False):
    forecast = []
    if run.forecast_json:
        try:
            forecast = json.loads(run.forecast_json)
        except (TypeError, ValueError):
            forecast = []
    return {"available": run.status == "completed", "run_id": run.id, "machine_id": run.machine_id, "reading_type": run.reading_type, "model": run.model, "horizon": run.horizon, "forecast": forecast, "next_prediction": run.next_prediction, "end_prediction": run.end_prediction, "trend": run.trend, "status": run.status, "trigger": run.trigger, "forecast_window": run.forecast_window, "step_seconds": run.step_seconds, "created_at": run.created_at.isoformat() if run.created_at else None, "input_ended_at": run.input_ended_at.isoformat() if run.input_ended_at else None, "input_reading_count": run.input_reading_count, "error_message": run.error_message, "reused": reused}


def automatic_forecast_for_reading(machine_id: int, reading_type: str):
    if not _truthy("ML_AUTO_FORECASTS", True):
        return None
    reading_type = (reading_type or "").strip().lower()
    if reading_type not in _signals():
        return None
    db = SessionLocal()
    try:
        machine = db.query(models.Machine).filter(models.Machine.id == machine_id, models.Machine.archived.is_(False)).first()
        if not machine:
            return None
        return _run_forecast(db, machine, reading_type, _model(), int(os.getenv("ML_FORECAST_HORIZON", "12")), "automatic")
    except Exception:
        db.rollback()
        return None
    finally:
        db.close()


# Windowed horizon forecasts share the same ML service and are registered on this router.
from .forecast_windows import router as forecast_windows_router
router.include_router(forecast_windows_router)
