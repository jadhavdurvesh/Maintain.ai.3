from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, audit
from ..database import get_db
from ..deps import get_current_user, CurrentUser

router = APIRouter(prefix="/api/machines", tags=["machines"])


def _recompute_status(machine: models.Machine):
    """Health score -> status, and derive next maintenance date from operating hours."""
    if machine.health_score >= 70:
        machine.status = models.HealthStatus.healthy
    elif machine.health_score >= 40:
        machine.status = models.HealthStatus.attention
    else:
        machine.status = models.HealthStatus.critical


def _get_scoped_machine(db: Session, machine_id: int, current: CurrentUser) -> models.Machine:
    """Fetch a machine, but only if it belongs to the caller's organization.
    In local mode (REQUIRE_AUTH=false) everything belongs to the bootstrap
    org, so this behaves exactly as a plain lookup. In multi-tenant mode,
    a machine belonging to a different organization returns 404 — the same
    response as "doesn't exist" — rather than 403, so it doesn't even leak
    that the ID is in use by someone else's company."""
    machine = db.get(models.Machine, machine_id)
    if not machine or machine.organization_id != current.organization_id:
        raise HTTPException(404, "machine not found")
    return machine


@router.get("", response_model=List[schemas.MachineOut])
def list_machines(
    include_archived: bool = False,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(models.Machine).filter_by(organization_id=current.organization_id)
    if not include_archived:
        q = q.filter_by(archived=False)
    return q.all()


@router.post("", response_model=schemas.MachineOut)
def create_machine(
    payload: schemas.MachineIn,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if db.query(models.Machine).filter_by(machine_code=payload.machine_code, organization_id=current.organization_id).first():
        raise HTTPException(400, "machine_code already exists")
    machine = models.Machine(**payload.model_dump(), organization_id=current.organization_id)
    machine.health_score = 100
    _recompute_status(machine)
    db.add(machine)
    db.commit()
    db.refresh(machine)
    audit.log_event(db, "machine", machine.id, "created", f"Machine {machine.name} ({machine.machine_code}) added")
    return machine


@router.get("/{machine_id}", response_model=schemas.MachineOut)
def get_machine(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_scoped_machine(db, machine_id, current)


@router.patch("/{machine_id}", response_model=schemas.MachineOut)
def update_machine(
    machine_id: int, payload: schemas.MachineUpdate,
    current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    machine = _get_scoped_machine(db, machine_id, current)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(machine, field, value)
    _recompute_status(machine)
    db.commit()
    db.refresh(machine)
    return machine


@router.delete("/{machine_id}")
def archive_machine(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Soft-delete: the machine and every fault/maintenance/work-order/reading
    tied to it stays in the database forever — it's just hidden from the
    active machine list. Nothing is ever actually destroyed here."""
    machine = _get_scoped_machine(db, machine_id, current)
    machine.archived = True
    db.commit()
    audit.log_event(db, "machine", machine.id, "archived", f"Machine {machine.name} ({machine.machine_code}) archived (history preserved)")
    return {"archived": True}


@router.post("/{machine_id}/restore")
def restore_machine(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    machine = _get_scoped_machine(db, machine_id, current)
    machine.archived = False
    db.commit()
    audit.log_event(db, "machine", machine.id, "restored", f"Machine {machine.name} ({machine.machine_code}) restored")
    return {"archived": False}


@router.post("/{machine_id}/components", response_model=schemas.ComponentOut)
def add_component(
    machine_id: int, payload: schemas.ComponentIn,
    current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    _get_scoped_machine(db, machine_id, current)
    component = models.Component(machine_id=machine_id, **payload.model_dump())
    db.add(component)
    db.commit()
    db.refresh(component)
    return component


@router.get("/{machine_id}/components", response_model=List[schemas.ComponentOut])
def list_components(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_scoped_machine(db, machine_id, current)
    return db.query(models.Component).filter_by(machine_id=machine_id).all()


@router.post("/{machine_id}/readings", response_model=schemas.SensorReadingOut)
def add_reading(
    machine_id: int, payload: schemas.SensorReadingIn,
    current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    _get_scoped_machine(db, machine_id, current)
    reading = models.SensorReading(machine_id=machine_id, **payload.model_dump())
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return reading


@router.get("/{machine_id}/readings", response_model=List[schemas.SensorReadingOut])
def list_readings(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_scoped_machine(db, machine_id, current)
    return (
        db.query(models.SensorReading)
        .filter_by(machine_id=machine_id)
        .order_by(models.SensorReading.recorded_at.desc())
        .all()
    )
