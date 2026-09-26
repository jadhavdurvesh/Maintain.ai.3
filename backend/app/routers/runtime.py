from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Session

from .. import audit, models
from ..database import Base, get_db
from ..deps import get_current_user, CurrentUser

router = APIRouter(prefix="/api/machines", tags=["machine-runtime"])

# Use the application's Base.metadata so the machines.id foreign key resolves
# correctly when the runtime table is created in the hosted backend.
runtime_states = Table(
    "machine_runtime_states",
    Base.metadata,
    Column("machine_id", Integer, ForeignKey("machines.id", ondelete="CASCADE"), primary_key=True),
    Column("state", String(24), nullable=False, default="stopped"),
    Column("started_at", DateTime, nullable=True),
    Column("base_operating_hours", Float, nullable=False, default=0),
    Column("updated_at", DateTime, nullable=False),
)

_ALLOWED_STATES = {"running", "idle", "stopped", "maintenance", "fault"}
_ACTIVE_STATE = "running"


def _ensure_table(db: Session):
    Base.metadata.create_all(bind=db.get_bind(), tables=[runtime_states], checkfirst=True)


def _is_runtime_manager(current: CurrentUser) -> bool:
    return current.role in {models.UserRole.admin.value, models.UserRole.technician.value}


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


def _snapshot(machine, row):
    return {
        "machine_id": machine.id,
        "state": row["state"],
        "operating_hours": round(_hours(machine, row), 4),
        "started_at": row["started_at"],
        "updated_at": row["updated_at"],
        "is_running": row["state"] == _ACTIVE_STATE,
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
    return [_snapshot(machine, _row(db, machine)) for machine in query.all()]


@router.get("/{machine_id}/runtime")
def get_runtime(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _ensure_table(db)
    machine = _get_machine(db, machine_id, current)
    return _snapshot(machine, _row(db, machine))


@router.post("/{machine_id}/runtime/{state}")
def set_runtime_state(machine_id: int, state: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if not _is_runtime_manager(current):
        raise HTTPException(status_code=403, detail="runtime control requires technician or administrator access")
    if state not in _ALLOWED_STATES:
        raise HTTPException(status_code=400, detail=f"invalid runtime state: {state}")

    _ensure_table(db)
    machine = _get_machine(db, machine_id, current)
    row = _row(db, machine)
    now = datetime.utcnow()
    settled_hours = _hours(machine, row, now)
    previous = row["state"]

    db.execute(runtime_states.update().where(runtime_states.c.machine_id == machine.id).values(
        state=state,
        started_at=now if state == _ACTIVE_STATE else None,
        base_operating_hours=settled_hours,
        updated_at=now,
    ))
    if state != _ACTIVE_STATE:
        machine.operating_hours = settled_hours
    db.commit()

    if previous != state:
        audit.log_event(db, "machine", machine.id, "runtime_state_changed",
                        f"Machine {machine.name} runtime changed from {previous} to {state}",
                        performed_by=current.username)
    return _snapshot(machine, _row(db, machine))
