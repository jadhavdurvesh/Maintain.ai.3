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
    """Normalize DB timestamps so hosted Postgres and local SQLite behave identically."""
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _ensure_table(db: Session):
    Base.metadata.create_all(bind=db.get_bind(), tables=[runtime_states], checkfirst=True)


def _fallback_row(machine):
    now = datetime.utcnow()
    return {
        "machine_id": machine.id,
        "state": "stopped",
        "started_at": None,
        "base_operating_hours": float(machine.operating_hours or 0),
        "updated_at": now,
    }


def _machine_is_assigned(db: Session, machine_id: int, current: CurrentUser) -> bool:
    if current.role != models.UserRole.technician.value:
        return True
    return db.query(models.UserMachineAssignment).filter(
        models.UserMachineAssignment.user_id == current.id,
        models.UserMachineAssignment.machine_id == machine_id,
    ).first() is not None


def _get_machine(db: Session, machine_id: int, current: CurrentUser):
    machine = db.query(models.Machine).filter(
        models.Machine.id == machine_id,
        models.Machine.organization_id == current.organization_id,
        models.Machine.archived.is_(False),
    ).first()
    if not machine or not _machine_is_assigned(db, machine_id, current):
        raise HTTPException(status_code=404, detail="machine not found")
    return machine


def _row(db: Session, machine):
    try:
        result = db.execute(runtime_states.select().where(runtime_states.c.machine_id == machine.id)).mappings().first()
        if result:
            return result
        now = datetime.utcnow()
        db.execute(runtime_states.insert().values(
            machine_id=machine.id,
            state="stopped",
            started_at=None,
            base_operating_hours=float(machine.operating_hours or 0),
            updated_at=now,
        ))
        db.commit()
        return db.execute(runtime_states.select().where(runtime_states.c.machine_id == machine.id)).mappings().first()
    except Exception:
        # A runtime bookkeeping failure must never take down /api/machines.
        db.rollback()
        return _fallback_row(machine)


def _hours(machine, row, now=None):
    base = float(row["base_operating_hours"] or 0)
    started_at = _utc_naive(row["started_at"])
    if row["state"] != _ACTIVE_STATE or not started_at:
        return base
    now = _utc_naive(now or datetime.utcnow())
    return base + max(0.0, (now - started_at).total_seconds()) / 3600.0


def _latest_reading(db: Session, machine_id: int, reading_type: str):
    try:
        return db.query(models.SensorReading).filter_by(
            machine_id=machine_id,
            reading_type=reading_type,
        ).order_by(models.SensorReading.recorded_at.desc(), models.SensorReading.id.desc()).first()
    except Exception:
        return None


def _has_unacknowledged_shutdown(db: Session, machine_id: int) -> bool:
    try:
        event = db.query(models.MachineSafetyEvent).filter_by(
            machine_id=machine_id,
            event_type="shutdown_threshold",
            shutdown_requested=True,
        ).order_by(models.MachineSafetyEvent.created_at.desc(), models.MachineSafetyEvent.id.desc()).first()
        return bool(event and not event.device_acknowledged)
    except Exception:
        # If the optional safety-event history is unavailable, runtime state
        # still needs to remain readable. Device safety endpoints remain the
        # authoritative shutdown path.
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
        db.execute(runtime_states.update().where(runtime_states.c.machine_id == machine.id).values(
            state=target_state,
            started_at=now if target_state == _ACTIVE_STATE else None,
            base_operating_hours=settled_hours,
            updated_at=now,
        ))
        machine.operating_hours = settled_hours
        db.flush()
        return db.execute(runtime_states.select().where(runtime_states.c.machine_id == machine.id)).mappings().first()
    except Exception:
        db.rollback()
        # Keep the API usable even if runtime persistence is temporarily unavailable.
        return {
            "machine_id": machine.id,
            "state": target_state,
            "started_at": now if target_state == _ACTIVE_STATE else None,
            "base_operating_hours": settled_hours,
            "updated_at": now,
        }


def _infer_target_state(db: Session, machine_id: int):
    current = _latest_reading(db, machine_id, "current")
    load = _latest_reading(db, machine_id, "load")
    vibration = _latest_reading(db, machine_id, "vibration")
    signals = [r for r in (current, load, vibration) if r is not None]
    if not signals:
        return None, None

    timestamps = [_utc_naive(r.recorded_at) for r in signals if r.recorded_at]
    if not timestamps:
        return None, None
    latest_signal_time = max(timestamps)
    if datetime.utcnow() - latest_signal_time > _TELEMETRY_TIMEOUT:
        return "stopped", latest_signal_time

    current_active = current is not None and float(current.value) > _ACTIVE_CURRENT_A
    load_active = load is not None and float(load.value) > _ACTIVE_LOAD_PERCENT
    vibration_active = vibration is not None and float(vibration.value) > _ACTIVE_VIBRATION_G
    if current_active or load_active or vibration_active:
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
    return {
        "machine_id": machine.id,
        "state": row["state"],
        "operating_hours": round(_hours(machine, row), 4),
        "started_at": row["started_at"],
        "updated_at": row["updated_at"],
        "is_running": row["state"] == _ACTIVE_STATE,
        "automatic": True,
    }


@router.get("/runtime")
def list_runtime(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_table(db)
    query = db.query(models.Machine).filter(
        models.Machine.organization_id == current.organization_id,
        models.Machine.archived.is_(False),
    )
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
