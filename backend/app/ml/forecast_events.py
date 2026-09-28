from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import event
from sqlalchemy.orm import Session

from ..models import SensorReading
from .forecasting import automatic_forecast_for_reading

# Keep inference out of the telemetry request path. The coordinator itself
# performs cadence and duplicate checks before contacting the ML service.
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="maintain-forecast")


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


@event.listens_for(Session, "after_rollback")
def _clear_sensor_forecasts(session: Session) -> None:
    session.info.pop("_maintain_forecast_readings", None)
