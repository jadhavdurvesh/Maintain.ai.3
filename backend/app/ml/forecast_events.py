from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import event, inspect, text
from sqlalchemy.orm import Session

from ..database import engine
from ..models import SensorReading
from .forecasting import automatic_forecast_for_reading
from .forecast_windows import automatic_forecast_windows_for_reading

# Forecast inference is intentionally throttled. Telemetry can arrive much more
# frequently than a useful prediction can change, and Vercel serverless workers
# must not launch several ML jobs for every sensor event.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="maintain-forecast")


def _auto_forecasts_enabled() -> bool:
    return os.getenv("ML_AUTO_FORECASTS", "true").strip().lower() in {"1", "true", "yes", "on"}


def _auto_signal(reading_type: str) -> bool:
    # Keep automatic inference focused on the primary health signal. The other
    # signals remain fully available through the manual prediction endpoints.
    allowed = os.getenv("ML_AUTO_FORECAST_SIGNALS", "temperature").strip().lower()
    return (reading_type or "").strip().lower() in {x.strip() for x in allowed.split(",") if x.strip()}


def _ensure_forecast_window_columns() -> None:
    try:
        inspector = inspect(engine)
        if not inspector.has_table("ml_forecast_runs"):
            return
        columns = {column["name"] for column in inspector.get_columns("ml_forecast_runs")}
        additions = []
        if "forecast_window" not in columns:
            additions.append("ALTER TABLE ml_forecast_runs ADD COLUMN forecast_window VARCHAR")
        if "step_seconds" not in columns:
            additions.append("ALTER TABLE ml_forecast_runs ADD COLUMN step_seconds INTEGER")
        if additions:
            with engine.begin() as connection:
                for statement in additions:
                    connection.execute(text(statement))
    except Exception:
        pass


_ensure_forecast_window_columns()


@event.listens_for(Session, "after_flush")
def _collect_sensor_readings(session: Session, flush_context) -> None:
    pending = session.info.setdefault("_maintain_forecast_readings", set())
    for obj in session.new:
        if isinstance(obj, SensorReading) and obj.source == "sensor" and obj.machine_id and obj.reading_type:
            pending.add((int(obj.machine_id), str(obj.reading_type)))


@event.listens_for(Session, "after_commit")
def _schedule_sensor_forecasts(session: Session) -> None:
    if not _auto_forecasts_enabled():
        session.info.pop("_maintain_forecast_readings", None)
        return
    pending = session.info.pop("_maintain_forecast_readings", set())
    for machine_id, reading_type in pending:
        if not _auto_signal(reading_type):
            continue
        # One lightweight automatic coordinator per telemetry event. It applies
        # its own freshness/cadence/duplicate checks before calling the ML host.
        _executor.submit(_run_automatic_forecast, machine_id, reading_type)


def _run_automatic_forecast(machine_id: int, reading_type: str) -> None:
    try:
        automatic_forecast_for_reading(machine_id, reading_type)
        # Long-range windows are expensive and are therefore not generated on
        # every telemetry event. They remain available through the explicit
        # window-run API and the UI can request them when needed.
    except Exception:
        # Forecasting must never affect telemetry ingestion.
        return


@event.listens_for(Session, "after_rollback")
def _clear_sensor_forecasts(session: Session) -> None:
    session.info.pop("_maintain_forecast_readings", None)
