from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, audit
from ..database import get_db
from ..deps import get_current_user, CurrentUser

router = APIRouter(
    prefix="/api/machines",
    tags=["machines"],
)


def _recompute_status(machine: models.Machine):
    """Keep machine health status aligned with its health score."""
    if machine.health_score >= 70:
        machine.status = models.HealthStatus.healthy
    elif machine.health_score >= 40:
        machine.status = models.HealthStatus.attention
    else:
        machine.status = models.HealthStatus.critical


def _is_worker(current: CurrentUser) -> bool:
    return (
        current.id is not None
        and current.role == models.UserRole.technician.value
    )


def _machine_is_assigned(
    db: Session,
    machine_id: int,
    current: CurrentUser,
) -> bool:
    """Check whether an authenticated worker owns this machine assignment."""
    if not _is_worker(current):
        return True

    return (
        db.query(models.UserMachineAssignment)
        .filter(
            models.UserMachineAssignment.user_id == current.id,
            models.UserMachineAssignment.machine_id == machine_id,
        )
        .first()
        is not None
    )


def _get_scoped_machine(
    db: Session,
    machine_id: int,
    current: CurrentUser,
) -> models.Machine:
    machine = (
        db.query(models.Machine)
        .filter(
            models.Machine.id == machine_id,
            models.Machine.organization_id
            == current.organization_id,
        )
        .first()
    )

    if not machine:
        raise HTTPException(
            status_code=404,
            detail="machine not found",
        )

    if not _machine_is_assigned(
        db,
        machine_id,
        current,
    ):
        raise HTTPException(
            status_code=404,
            detail="machine not assigned to this worker",
        )

    return machine


@router.get(
    "",
    response_model=List[schemas.MachineOut],
)
def list_machines(
    include_archived: bool = False,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(models.Machine).filter(
        models.Machine.organization_id
        == current.organization_id
    )

    if not include_archived:
        q = q.filter(
            models.Machine.archived.is_(False)
        )

    # Technicians only see their assigned machines.
    if _is_worker(current):
        q = q.join(
            models.UserMachineAssignment,
            models.UserMachineAssignment.machine_id
            == models.Machine.id,
        ).filter(
            models.UserMachineAssignment.user_id
            == current.id
        )

    return q.order_by(
        models.Machine.name.asc()
    ).all()


@router.post(
    "",
    response_model=schemas.MachineOut,
)
def create_machine(
    payload: schemas.MachineIn,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current.role != models.UserRole.admin.value:
        raise HTTPException(
            status_code=403,
            detail="administrator access required",
        )

    if (
        db.query(models.Machine)
        .filter(
            models.Machine.machine_code
            == payload.machine_code,
            models.Machine.organization_id
            == current.organization_id,
        )
        .first()
    ):
        raise HTTPException(
            status_code=400,
            detail="machine_code already exists",
        )

    machine = models.Machine(
        **payload.model_dump(),
        organization_id=current.organization_id,
    )

    machine.health_score = 100
    _recompute_status(machine)

    db.add(machine)
    db.commit()
    db.refresh(machine)

    audit.log_event(
        db,
        "machine",
        machine.id,
        "created",
        f"Machine {machine.name} "
        f"({machine.machine_code}) added",
        performed_by=current.username,
    )

    return machine


@router.get(
    "/{machine_id}",
    response_model=schemas.MachineOut,
)
def get_machine(
    machine_id: int,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_scoped_machine(
        db,
        machine_id,
        current,
    )


@router.patch(
    "/{machine_id}",
    response_model=schemas.MachineOut,
)
def update_machine(
    machine_id: int,
    payload: schemas.MachineUpdate,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Workers can view machines but cannot modify them.
    if current.role != models.UserRole.admin.value:
        raise HTTPException(
            status_code=403,
            detail="administrator access required",
        )

    machine = _get_scoped_machine(
        db,
        machine_id,
        current,
    )

    for field, value in payload.model_dump(
        exclude_unset=True
    ).items():
        setattr(
            machine,
            field,
            value,
        )

    _recompute_status(machine)

    db.commit()
    db.refresh(machine)

    return machine


@router.delete(
    "/{machine_id}",
)
def archive_machine(
    machine_id: int,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current.role != models.UserRole.admin.value:
        raise HTTPException(
            status_code=403,
            detail="administrator access required",
        )

    machine = _get_scoped_machine(
        db,
        machine_id,
        current,
    )

    machine.archived = True

    db.commit()

    audit.log_event(
        db,
        "machine",
        machine.id,
        "archived",
        f"Machine {machine.name} "
        f"({machine.machine_code}) archived "
        "(history preserved)",
        performed_by=current.username,
    )

    return {
        "archived": True,
    }


@router.post(
    "/{machine_id}/restore",
)
def restore_machine(
    machine_id: int,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current.role != models.UserRole.admin.value:
        raise HTTPException(
            status_code=403,
            detail="administrator access required",
        )

    machine = _get_scoped_machine(
        db,
        machine_id,
        current,
    )

    machine.archived = False

    db.commit()

    audit.log_event(
        db,
        "machine",
        machine.id,
        "restored",
        f"Machine {machine.name} "
        f"({machine.machine_code}) restored",
        performed_by=current.username,
    )

    return {
        "archived": False,
    }


@router.post(
    "/{machine_id}/components",
    response_model=schemas.ComponentOut,
)
def add_component(
    machine_id: int,
    payload: schemas.ComponentIn,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current.role != models.UserRole.admin.value:
        raise HTTPException(
            status_code=403,
            detail="administrator access required",
        )

    _get_scoped_machine(
        db,
        machine_id,
        current,
    )

    component = models.Component(
        machine_id=machine_id,
        **payload.model_dump(),
    )

    db.add(component)
    db.commit()
    db.refresh(component)

    return component


@router.get(
    "/{machine_id}/components",
    response_model=List[schemas.ComponentOut],
)
def list_components(
    machine_id: int,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_scoped_machine(
        db,
        machine_id,
        current,
    )

    return (
        db.query(models.Component)
        .filter(
            models.Component.machine_id
            == machine_id
        )
        .all()
    )


@router.post(
    "/{machine_id}/readings",
    response_model=schemas.SensorReadingOut,
)
def add_reading(
    machine_id: int,
    payload: schemas.SensorReadingIn,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current.role != models.UserRole.admin.value:
        raise HTTPException(
            status_code=403,
            detail="administrator access required",
        )

    _get_scoped_machine(
        db,
        machine_id,
        current,
    )

    reading = models.SensorReading(
        machine_id=machine_id,
        **payload.model_dump(),
    )

    db.add(reading)
    db.commit()
    db.refresh(reading)

    return reading


@router.get(
    "/{machine_id}/readings",
    response_model=List[schemas.SensorReadingOut],
)
def list_readings(
    machine_id: int,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_scoped_machine(
        db,
        machine_id,
        current,
    )

    return (
        db.query(models.SensorReading)
        .filter(
            models.SensorReading.machine_id
            == machine_id
        )
        .order_by(
            models.SensorReading.recorded_at.desc()
        )
        .all()
    )