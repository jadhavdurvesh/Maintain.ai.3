from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Session

from .. import models
from ..database import Base, get_db
from ..deps import get_current_user, CurrentUser

router = APIRouter(prefix="/api/machines", tags=["machine-runtime"])

# Runtime is derived from machine telemetry. The machine.status field remains
# the health status; this table tracks whether the asset is actually consuming
# operating hours.
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
_TELEMETRY_TIMEOUT = timedelta(seconds=90)


def _ensure_table(db: Session):
    Base.metadata.create_all(bind=db.get_bind(), tables=[runtime_states], checkfirst=True)


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


def _hours(machine, row, now=None):
    base = float(row["base_operating_hours"] or 0)
    if row["state"] != _ACTIVE_STATE or not row["started_at"]:
        return base
    now = now or datetime.utcnow()
    return base + max(0.0, (now - row["started_at"]).total_seconds()) / 3600.0


def _latest_reading(db: Session, machine_id: int, reading_type: str):
    return (
        db.query(models.SensorReading)
        .filter_by(machine_id=machine_id, reading_type=reading_type)
        .order_by(models.SensorReading.recorded_at.desc(), models.SensorReading.id.desc())
        .first()
    )


def _latest_any_reading(db: Session, machine_id: int):
    return (
        db.query(models.SensorReading)
        .filter_by(machine_id=machine_id)
        .order_by(models.SensorReading.recorded_at.desc(), models.SensorReading.id.desc())
        .first()
    )


def _has_unacknowledged_shutdown(db: Session, machine_id: int) -> bool:
    event = (
        db.query(models.MachineSafetyEvent)
        .filter_by(machine_id=machine_id, event_type="shutdown_threshold", shutdown_requested=True)
        .order_by(models.MachineSafetyEvent.created_at.desc(), models.MachineSafetyEvent.id.desc())
        .first()
    )
    return bool(event and not event.device_acknowledged)


def _apply_state(db: Session, machine, row, target_state: str, now=None):
    """Settle accumulated hours and transition state without user controls."""
    now = now or datetime.utcnow()
    previous = row["state"]
    settled_hours = _hours(machine, row, now)

    if target_state == _ACTIVE_STATE:
        if previous != _ACTIVE_STATE:
            values = {
                "state": _ACTIVE_STATE,
                "started_at": now,
                "base_operating_hours": settled_hours,
                "updated_at": now,
            }
        else:
            values = {"updated_at": now}
        machine.operating_hours = settled_hours
    else:
        values = {
            "state": target_state,
            "started_at": None,
            "base_operating_hours": settled_hours,
            "updated_at": now,
        }
        machine.operating_hours = settled_hours

    if any(values.get(key) != row[key] for key in values if key in row):
        db.execute(runtime_states.update().where(runtime_states.c.machine_id == machine.id).values(**values))
        row = db.execute(runtime_states.select().where(runtime_states.c.machine_id == machine.id)).mappings().first()
    else:
        row = dict(row)
    db.flush()
    return row


def sync_runtime_from_reading(db: Session, machine, reading):
    """Infer runtime from current/load telemetry; called after every device reading."""
    _ensure_table(db)
    row = _row(db, machine)
    now = reading.recorded_at or datetime.utcnow()

    # An unacknowledged automatic safety shutdown always wins over normal
    # sensor-derived activity. This makes the machine visibly STOPPED as soon
    # as the safety system latches it off.
    if _has_unacknowledged_shutdown(db, machine.id):
        return _apply_state(db, machine, row, "stopped", now)

    current = _latest_reading(db, machine.id, "current")
    load = _latest_reading(db, machine.id, "load")
    signals = [r for r in (current, load) if r is not None]
    if not signals:
        return row

    latest_signal_time = max(r.recorded_at for r in signals if r.recorded_at)
    if now - latest_signal_time > _TELEMETRY_TIMEOUT:
        target = "stopped"
    else:
        current_active = current is not None and float(current.value) > _ACTIVE_CURRENT_A
        load_active = load is not None and float(load.value) > _ACTIVE_LOAD_PERCENT
        target = "running" if (current_active or load_active) else "idle"

    return _apply_state(db, machine, row, target, now)


def _sync_runtime_from_latest_telemetry(db: Session, machine):
    """Reconcile state for list/detail requests, including telemetry timeouts."""
    _ensure_table(db)
    row = _row(db, machine)
    now = datetime.utcnow()

    if _has_unacknowledged_shutdown(db, machine.id):
        return _apply_state(db, machine, row, "stopped", now)

    current = _latest_reading(db, machine.id, "current")
    load = _latest_reading(db, machine.id, "load")
    signals = [r for r in (current, load) if r is not None]
    if not signals:
        return row

    latest_signal_time = max(r.recorded_at for r in signals if r.recorded_at)
    if now - latest_signal_time > _TELEMETRY_TIMEOUT:
        return _apply_state(db, machine, row, "stopped", now)

    current_active = current is not None and float(current.value) > _ACTIVE_CURRENT_A
    load_active = load is not None and float(load.value) > _ACTIVE_LOAD_PERCENT
    return _apply_state(db, machine, row, "running" if (current_active or load_active) else "idle", now)


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
        query = query.join(models.UserMachineAssignment, models.UserMachineAssignment.machine_id == models.Machine.id).filter(
            models.UserMachineAssignment.user_id == current.id
        )
    machines = query.all()
    snapshots = []
    for machine in machines:
        row = _sync_runtime_from_latest_telemetry(db, machine)
        snapshots.append(_snapshot(machine, row))
    db.commit()
    return snapshots


@router.get("/{machine_id}/runtime")
def get_runtime(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_table(db)
    machine = _get_machine(db, machine_id, current)
    row = _sync_runtime_from_latest_telemetry(db, machine)
    db.commit()
    return _snapshot(machine, row)
