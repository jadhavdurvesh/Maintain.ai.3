from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import event, inspect, text
from sqlalchemy.orm import Session

from ..database import engine
from ..models import SensorReading
from .forecasting import automatic_forecast_for_reading
from .forecast_windows import automatic_forecast_windows_for_reading

# Keep inference out of the telemetry request path. Coordinators perform
# cadence, duplicate, and telemetry-availability checks before contacting ML.
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="maintain-forecast")


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
    pending = session.info.pop("_maintain_forecast_readings", set())
    for machine_id, reading_type in pending:
        _executor.submit(automatic_forecast_for_reading, machine_id, reading_type)
        _executor.submit(automatic_forecast_windows_for_reading, machine_id, reading_type)


@event.listens_for(Session, "after_rollback")
def _clear_sensor_forecasts(session: Session) -> None:
    session.info.pop("_maintain_forecast_readings", None)
