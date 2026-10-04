from datetime import datetime, timezone
from sqlalchemy.orm import Session
from . import models

ACTIVE_TYPES = {
    "current", "motor_current", "load", "motor_load", "pump_load", "spindle_load",
    "speed", "fan_speed", "rpm", "spindle_rpm", "wheel_rpm", "vibration", "spindle_vibration",
    "chuck_vibration", "line_speed", "conveyor_speed", "print_speed", "extrusion_rate",
    "hydraulic_pressure", "injection_pressure", "steam_pressure", "pressure", "utilization",
}

def _naive(value):
    if value is None:
        return None
    if value.tzinfo:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value

def period_bounds(month: str):
    start = datetime.strptime(month + "-01", "%Y-%m-%d")
    if start.month == 12:
        end = datetime(start.year + 1, 1, 1)
    else:
        end = datetime(start.year, start.month + 1, 1)
    return start, end

def _running(reading):
    kind = str(reading.reading_type or "").lower()
    value = abs(float(reading.value or 0))
    if kind in {"current", "motor_current"}:
        return value > 0.5
    if kind in {"load", "motor_load", "pump_load", "spindle_load", "fan_speed", "speed", "line_speed", "conveyor_speed", "print_speed", "extrusion_rate", "utilization"}:
        return value > 5
    if kind in {"rpm", "spindle_rpm", "wheel_rpm", "screw_rpm"}:
        return value > 1
    if kind in {"vibration", "spindle_vibration", "chuck_vibration"}:
        return value > 0.05
    if kind in {"hydraulic_pressure", "injection_pressure", "steam_pressure", "pressure"}:
        return value > 1
    return False

def telemetry_runtime_hours(db: Session, machine_id: int, start: datetime, end: datetime):
    readings = db.query(models.SensorReading).filter(
        models.SensorReading.machine_id == machine_id,
        models.SensorReading.recorded_at >= start,
        models.SensorReading.recorded_at < end,
        models.SensorReading.reading_type.in_(ACTIVE_TYPES),
    ).order_by(models.SensorReading.recorded_at.asc(), models.SensorReading.id.asc()).all()
    by_time = {}
    for reading in readings:
        by_time[_naive(reading.recorded_at)] = reading
    points = sorted(by_time.items())
    if len(points) < 2:
        return None
    seconds = 0.0
    for (t1, r1), (t2, _) in zip(points, points[1:]):
        gap = (t2 - t1).total_seconds()
        if 0 < gap <= 300 and _running(r1):
            seconds += gap
    return seconds / 3600.0
