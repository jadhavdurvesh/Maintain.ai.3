from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, audit
from ..database import get_db
from ..deps import get_current_user, CurrentUser
from ..alerts_engine import evaluate_machine

router = APIRouter(
    prefix="/api/faults",
    tags=["faults"],
)


def _is_worker(current: CurrentUser) -> bool:
    return (
        current.id is not None
        and current.role == models.UserRole.technician.value
    )


def _get_machine(
    machine_id: int,
    current: CurrentUser,
    db: Session,
) -> models.Machine:
    machine = (
        db.query(models.Machine)
        .filter(
            models.Machine.id == machine_id,
            models.Machine.organization_id
            == current.organization_id,
            models.Machine.archived.is_(False),
        )
        .first()
    )

    if not machine:
        raise HTTPException(
            status_code=404,
            detail="machine not found",
        )

    if _is_worker(current):
        assignment = (
            db.query(models.UserMachineAssignment)
            .filter(
                models.UserMachineAssignment.user_id
                == current.id,
                models.UserMachineAssignment.machine_id
                == machine.id,
            )
            .first()
        )

        if not assignment:
            raise HTTPException(
                status_code=404,
                detail="machine not assigned to this worker",
            )

    return machine


@router.get(
    "",
    response_model=List[schemas.FaultRecordOut],
)
def list_faults(
    machine_id: int | None = None,
    unresolved_only: bool = False,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(models.FaultRecord)
        .join(models.Machine)
        .filter(
            models.Machine.organization_id
            == current.organization_id,
        )
    )

    if _is_worker(current):
        query = query.join(
            models.UserMachineAssignment,
            models.UserMachineAssignment.machine_id
            == models.Machine.id,
        ).filter(
            models.UserMachineAssignment.user_id
            == current.id,
        )

    if machine_id is not None:
        query = query.filter(
            models.FaultRecord.machine_id
            == machine_id,
        )

    if unresolved_only:
        query = query.filter(
            models.FaultRecord.resolved_date.is_(None),
        )

    return (
        query
        .order_by(
            models.FaultRecord.reported_date.desc(),
        )
        .all()
    )


@router.post(
    "",
    response_model=schemas.FaultRecordOut,
)
def create_fault(
    payload: schemas.FaultRecordIn,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    machine = _get_machine(
        payload.machine_id,
        current,
        db,
    )

    fault = models.FaultRecord(
        **payload.model_dump(),
    )

    db.add(fault)
    db.commit()
    db.refresh(fault)

    audit.log_event(
        db,
        "fault",
        fault.id,
        "reported",
        (
            f"Fault reported for {machine.name}: "
            f"{fault.description}"
        ),
        performed_by=current.username,
    )

    # Re-evaluate the machine after a new fault is reported.
    evaluate_machine(
        db,
        machine,
    )

    return fault


@router.post(
    "/{fault_id}/resolve",
    response_model=schemas.FaultRecordOut,
)
def resolve_fault(
    fault_id: int,
    payload: schemas.FaultResolveIn,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    fault = (
        db.query(models.FaultRecord)
        .join(models.Machine)
        .filter(
            models.FaultRecord.id == fault_id,
            models.Machine.organization_id
            == current.organization_id,
        )
        .first()
    )

    if not fault:
        raise HTTPException(
            status_code=404,
            detail="fault not found",
        )

    if _is_worker(current):
        # Workers can only resolve faults belonging
        # to machines assigned to them.
        assignment = (
            db.query(models.UserMachineAssignment)
            .filter(
                models.UserMachineAssignment.user_id
                == current.id,
                models.UserMachineAssignment.machine_id
                == fault.machine_id,
            )
            .first()
        )

        if not assignment:
            raise HTTPException(
                status_code=404,
                detail="fault is outside this worker's assignments",
            )

    if fault.resolved_date is not None:
        raise HTTPException(
            status_code=409,
            detail="fault is already resolved",
        )

    if payload.cause:
        fault.cause = payload.cause

    fault.resolution = payload.resolution
    fault.resolved_date = datetime.utcnow()

    db.commit()
    db.refresh(fault)

    audit.log_event(
        db,
        "fault",
        fault.id,
        "resolved",
        (
            f"Fault resolved for "
            f"{fault.machine.name}: "
            f"{fault.resolution}"
        ),
        performed_by=current.username,
    )

    return fault


@router.post(
    "/{fault_id}/work-order",
    response_model=schemas.WorkOrderOut,
)
def create_work_order_from_fault(
    fault_id: int,
    payload: schemas.WorkOrderIn | None = None,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    fault = (
        db.query(models.FaultRecord)
        .join(models.Machine)
        .filter(
            models.FaultRecord.id == fault_id,
            models.Machine.organization_id
            == current.organization_id,
        )
        .first()
    )

    if not fault:
        raise HTTPException(
            status_code=404,
            detail="fault not found",
        )

    if _is_worker(current):
        # Workers may report faults but cannot create
        # management work orders from them.
        assignment = (
            db.query(models.UserMachineAssignment)
            .filter(
                models.UserMachineAssignment.user_id
                == current.id,
                models.UserMachineAssignment.machine_id
                == fault.machine_id,
            )
            .first()
        )

        if not assignment:
            raise HTTPException(
                status_code=404,
                detail="fault is outside this worker's assignments",
            )

        raise HTTPException(
            status_code=403,
            detail=(
                "workers cannot create work orders "
                "from faults"
            ),
        )

    # Prevent duplicate active work orders for the same fault.
    existing = (
        db.query(models.WorkOrder)
        .filter(
            models.WorkOrder.fault_id == fault.id,
            models.WorkOrder.status.in_(
                [
                    models.WorkOrderStatus.pending,
                    models.WorkOrderStatus.in_progress,
                ]
            ),
        )
        .order_by(
            models.WorkOrder.created_at.desc()
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                "an active work order already exists "
                f"(#{existing.id})"
            ),
        )

    priority = (
        fault.severity.value
        if hasattr(fault.severity, "value")
        else str(fault.severity)
    )

    if priority == "warning":
        priority = "medium"

    if priority not in {
        "low",
        "medium",
        "high",
        "critical",
    }:
        priority = "medium"

    data = (
        payload.model_dump()
        if payload
        else {}
    )

    data["machine_id"] = fault.machine_id
    data["fault_id"] = fault.id

    data["problem"] = (
        data.get("problem")
        or fault.description
    )

    data["priority"] = (
        data.get("priority")
        or priority
    )

    data["recommended_actions"] = (
        data.get("recommended_actions")
        or (
            f"Investigate fault: {fault.symptoms}"
            if fault.symptoms
            else "Investigate reported fault and confirm root cause."
        )
    )

    assigned_to = data.get("assigned_to")

    if assigned_to:
        assignee = (
            db.query(models.User)
            .filter(
                models.User.username
                == assigned_to,
                models.User.organization_id
                == current.organization_id,
                models.User.active.is_(True),
            )
            .first()
        )

        if not assignee:
            raise HTTPException(
                status_code=400,
                detail="assigned user not found or inactive",
            )

        if assignee.role == models.UserRole.viewer:
            raise HTTPException(
                status_code=400,
                detail="viewers cannot be assigned maintenance work",
            )

    work_order = models.WorkOrder(
        **data,
    )

    db.add(work_order)
    db.commit()
    db.refresh(work_order)

    audit.log_event(
        db,
        "fault",
        fault.id,
        "work_order_created",
        (
            f"Work order #{work_order.id} "
            f"created from fault #{fault.id}"
            + (
                f" and assigned to {work_order.assigned_to}"
                if work_order.assigned_to
                else ""
            )
        ),
        performed_by=current.username,
    )

    return work_order