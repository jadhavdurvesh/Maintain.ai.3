from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Session

from .. import models
from ..database import Base, get_db
from ..deps import get_current_user, CurrentUser

router = APIRouter(prefix="/api/machines", tags=["machine-runtime"])

runtime_states = Table(
    "machine_runtime_states",
    Base.metadata,
    Column("machine_id", Integer, ForeignKey("machines.id", ondelete="CASCADE"), primary_key=True),
    Column("state", String(24), nullable=False, default="stopped"),
    Column("started_at", DateTime, nullable=True),
    Column("base_operating_hours", Float, nullable=False, default=0),
    Column("updated_at", DateTime, nullable=False),
)

_ACTIVE_STATE = "running"
_ACTIVE_CURRENT_A = 0.5
_ACTIVE_LOAD_PERCENT = 5.0
_ACTIVE_VIBRATION_G = 0.05
_TELEMETRY_TIMEOUT = timedelta(seconds=90)


def _utc_naive(value):
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _ensure_table(db: Session):
    Base.metadata.create_all(bind=db.get_bind(), tables=[runtime_states], checkfirst=True)


def _fallback_row(machine):
    now = datetime.utcnow()
    return {"machine_id": machine.id, "state": "stopped", "started_at": None, "base_operating_hours": float(machine.operating_hours or 0), "updated_at": now}


def _machine_is_assigned(db: Session, machine_id: int, current: CurrentUser) -> bool:
    if current.role != models.UserRole.technician.value:
        return True
    return db.query(models.UserMachineAssignment).filter(models.UserMachineAssignment.user_id == current.id, models.UserMachineAssignment.machine_id == machine_id).first() is not None


def _get_machine(db: Session, machine_id: int, current: CurrentUser):
    machine = db.query(models.Machine).filter(models.Machine.id == machine_id, models.Machine.organization_id == current.organization_id, models.Machine.archived.is_(False)).first()
    if not machine or not _machine_is_assigned(db, machine_id, current):
        raise HTTPException(status_code=404, detail="machine not found")
    return machine


def _row(db: Session, machine):
    try:
        result = db.execute(runtime_states.select().where(runtime_states.c.machine_id == machine.id)).mappings().first()
        if result:
            return result
        now = datetime.utcnow()
        db.execute(runtime_states.insert().values(machine_id=machine.id, state="stopped", started_at=None, base_operating_hours=float(machine.operating_hours or 0), updated_at=now))
        db.commit()
        return db.execute(runtime_states.select().where(runtime_states.c.machine_id == machine.id)).mappings().first()
    except Exception:
        db.rollback()
        return _fallback_row(machine)


def _hours(machine, row, now=None):
    base = float(row["base_operating_hours"] or 0)
    started_at = _utc_naive(row["started_at"])
    if row["state"] != _ACTIVE_STATE or not started_at:
        return base
    now = _utc_naive(now or datetime.utcnow())
    return base + max(0.0, (now - started_at).total_seconds()) / 3600.0


def _has_unacknowledged_shutdown(db: Session, machine_id: int) -> bool:
    try:
        event = db.query(models.MachineSafetyEvent).filter_by(machine_id=machine_id, event_type="shutdown_threshold", shutdown_requested=True).order_by(models.MachineSafetyEvent.created_at.desc(), models.MachineSafetyEvent.id.desc()).first()
        return bool(event and not event.device_acknowledged)
    except Exception:
        return False


def _apply_state(db: Session, machine, row, target_state: str, now=None):
    now = _utc_naive(now or datetime.utcnow())
    if target_state == _ACTIVE_STATE and row["state"] == _ACTIVE_STATE:
        try:
            db.execute(runtime_states.update().where(runtime_states.c.machine_id == machine.id).values(updated_at=now))
            db.flush()
            return db.execute(runtime_states.select().where(runtime_states.c.machine_id == machine.id)).mappings().first()
        except Exception:
            db.rollback()
            return row
    settled_hours = _hours(machine, row, now)
    try:
        db.execute(runtime_states.update().where(runtime_states.c.machine_id == machine.id).values(state=target_state, started_at=now if target_state == _ACTIVE_STATE else None, base_operating_hours=settled_hours, updated_at=now))
        machine.operating_hours = settled_hours
        db.flush()
        return db.execute(runtime_states.select().where(runtime_states.c.machine_id == machine.id)).mappings().first()
    except Exception:
        db.rollback()
        return {"machine_id": machine.id, "state": target_state, "started_at": now if target_state == _ACTIVE_STATE else None, "base_operating_hours": settled_hours, "updated_at": now}


def _infer_target_state(db: Session, machine_id: int):
    """Infer runtime from the latest telemetry, including all supported robot profiles."""
    active_types = {
        "current", "load", "spindle_load", "motor_load", "pump_load", "burner_load",
        "fan_speed", "speed", "line_speed", "conveyor_speed", "spindle_rpm", "wheel_rpm",
        "rpm", "screw_rpm", "joint_1", "joint_1_position", "hydraulic_pressure",
        "injection_pressure", "steam_pressure", "vibration", "spindle_vibration", "chuck_vibration",
        # Robot profile signals
        "base_angle", "radial_position", "vertical_position", "base_current", "radial_current",
        "vertical_current", "j1_position", "j2_position", "j3_position", "j4_position", "j5_position",
        "j6_position", "j1_angle", "j2_angle", "z_position", "theta", "z_force", "x_position",
        "y_position", "x_velocity", "y_velocity", "z_velocity", "x_current", "y_current", "z_current",
        "arm_a_position", "arm_b_position", "arm_c_position", "arm_a_current", "arm_b_current",
        "arm_c_current", "end_effector_position", "shoulder_angle", "wrist_angle", "shoulder_current",
        "radial_current", "joint_2_position", "joint_3_position", "joint_4_position", "joint_5_position",
        "joint_6_position", "joint_torque", "external_force", "tcp_speed", "motor_current",
    }
    try:
        readings = db.query(models.SensorReading).filter(models.SensorReading.machine_id == machine_id).order_by(models.SensorReading.recorded_at.desc(), models.SensorReading.id.desc()).limit(96).all()
    except Exception:
        return None, None
    latest_by_type = {}
    for reading in readings:
        if reading.reading_type not in latest_by_type:
            latest_by_type[reading.reading_type] = reading
    signals = [r for reading_type, r in latest_by_type.items() if reading_type in active_types]
    if not signals:
        return None, None
    timestamps = [_utc_naive(r.recorded_at) for r in signals if r.recorded_at]
    if not timestamps:
        return None, None
    latest_signal_time = max(timestamps)
    if datetime.utcnow() - latest_signal_time > _TELEMETRY_TIMEOUT:
        return "stopped", latest_signal_time
    for reading in signals:
        value = float(reading.value)
        kind = reading.reading_type
        if kind in {"current", "motor_current", "base_current", "radial_current", "vertical_current", "x_current", "y_current", "z_current", "servo_current", "j1_torque", "j2_torque", "j3_torque", "joint_torque", "arm_a_current", "arm_b_current", "arm_c_current", "external_force"} and abs(value) > _ACTIVE_CURRENT_A:
            return "running", latest_signal_time
        if kind in {"load", "spindle_load", "motor_load", "pump_load", "burner_load", "fan_speed", "speed", "line_speed", "conveyor_speed", "utilization"} and abs(value) > _ACTIVE_LOAD_PERCENT:
            return "running", latest_signal_time
        if kind in {"spindle_rpm", "wheel_rpm", "rpm", "screw_rpm", "joint_1", "joint_1_position", "j1_position", "j2_position", "j3_position", "j4_position", "j5_position", "j6_position", "j1_angle", "j2_angle", "x_velocity", "y_velocity", "z_velocity", "arm_a_position", "arm_b_position", "arm_c_position", "end_effector_position", "radial_position", "vertical_position", "base_angle", "shoulder_angle", "wrist_angle", "theta", "x_position", "y_position", "z_position"} and abs(value) > 1:
            return "running", latest_signal_time
        if kind in {"hydraulic_pressure", "injection_pressure", "steam_pressure", "pressure"} and value > 1:
            return "running", latest_signal_time
        if kind in {"vibration", "spindle_vibration", "chuck_vibration"} and value > _ACTIVE_VIBRATION_G:
            return "running", latest_signal_time
    return "idle", latest_signal_time


def sync_runtime_from_reading(db: Session, machine, reading):
    try:
        _ensure_table(db)
        row = _row(db, machine)
        now = _utc_naive(reading.recorded_at or datetime.utcnow())
        if _has_unacknowledged_shutdown(db, machine.id):
            return _apply_state(db, machine, row, "stopped", now)
        target, _ = _infer_target_state(db, machine.id)
        return row if target is None else _apply_state(db, machine, row, target, now)
    except Exception:
        db.rollback()
        return _fallback_row(machine)


def _sync_runtime_from_latest_telemetry(db: Session, machine):
    try:
        _ensure_table(db)
        row = _row(db, machine)
        now = datetime.utcnow()
        if _has_unacknowledged_shutdown(db, machine.id):
            return _apply_state(db, machine, row, "stopped", now)
        target, _ = _infer_target_state(db, machine.id)
        return row if target is None else _apply_state(db, machine, row, target, now)
    except Exception:
        db.rollback()
        return _fallback_row(machine)


def _snapshot(machine, row):
    return {"machine_id": machine.id, "state": row["state"], "operating_hours": round(_hours(machine, row), 4), "started_at": row["started_at"], "updated_at": row["updated_at"], "is_running": row["state"] == _ACTIVE_STATE, "automatic": True}


@router.get("/runtime")
def list_runtime(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_table(db)
    query = db.query(models.Machine).filter(models.Machine.organization_id == current.organization_id, models.Machine.archived.is_(False))
    if current.role == models.UserRole.technician.value:
        query = query.join(models.UserMachineAssignment, models.UserMachineAssignment.machine_id == models.Machine.id).filter(models.UserMachineAssignment.user_id == current.id)
    snapshots = [_snapshot(machine, _sync_runtime_from_latest_telemetry(db, machine)) for machine in query.all()]
    db.commit()
    return snapshots


@router.get("/{machine_id}/runtime")
def get_runtime(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_table(db)
    machine = _get_machine(db, machine_id, current)
    row = _sync_runtime_from_latest_telemetry(db, machine)
    db.commit()
    return _snapshot(machine, row)
