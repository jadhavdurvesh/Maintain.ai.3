from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, audit
from ..database import get_db
from ..deps import get_current_user, CurrentUser

router = APIRouter(
    prefix="/api/work-orders",
    tags=["work_orders"],
)


def _is_worker(current: CurrentUser) -> bool:
    return (
        current.id is not None
        and current.role == models.UserRole.technician.value
    )


def validate_assignee(
    assigned_to: str | None,
    current: CurrentUser,
    db: Session,
):
    if not assigned_to:
        return

    assignee = (
        db.query(models.User)
        .filter(
            models.User.username == assigned_to,
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


def _get_work_order(
    wo_id: int,
    current: CurrentUser,
    db: Session,
) -> models.WorkOrder:
    work_order = (
        db.query(models.WorkOrder)
        .join(models.Machine)
        .filter(
            models.WorkOrder.id == wo_id,
            models.Machine.organization_id
            == current.organization_id,
        )
        .first()
    )

    if not work_order:
        raise HTTPException(
            status_code=404,
            detail="work order not found",
        )

    # Workers may only access jobs assigned to them.
    if _is_worker(current):
        if work_order.assigned_to != current.username:
            raise HTTPException(
                status_code=404,
                detail="work order not assigned to this worker",
            )

    return work_order


@router.get(
    "",
    response_model=List[schemas.WorkOrderOut],
)
def list_work_orders(
    status: str | None = None,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(models.WorkOrder)
        .join(models.Machine)
        .filter(
            models.Machine.organization_id
            == current.organization_id,
        )
    )

    if _is_worker(current):
        query = query.filter(
            models.WorkOrder.assigned_to
            == current.username,
        )

    if status:
        query = query.filter(
            models.WorkOrder.status == status,
        )

    return (
        query
        .order_by(
            models.WorkOrder.created_at.desc(),
        )
        .all()
    )


@router.post(
    "",
    response_model=schemas.WorkOrderOut,
)
def create_work_order(
    payload: schemas.WorkOrderIn,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Workers cannot create or assign management work orders.
    if _is_worker(current):
        raise HTTPException(
            status_code=403,
            detail="workers cannot create work orders",
        )

    machine = db.get(
        models.Machine,
        payload.machine_id,
    )

    if (
        not machine
        or machine.organization_id
        != current.organization_id
    ):
        raise HTTPException(
            status_code=404,
            detail="machine not found",
        )

    if payload.fault_id:
        fault = db.get(
            models.FaultRecord,
            payload.fault_id,
        )

        if (
            not fault
            or fault.machine_id != machine.id
        ):
            raise HTTPException(
                status_code=400,
                detail="fault does not belong to this machine",
            )

        existing = (
            db.query(models.WorkOrder)
            .filter(
                models.WorkOrder.fault_id
                == fault.id,
                models.WorkOrder.status.in_(
                    [
                        models.WorkOrderStatus.pending,
                        models.WorkOrderStatus.in_progress,
                    ]
                ),
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

    validate_assignee(
        payload.assigned_to,
        current,
        db,
    )

    work_order = models.WorkOrder(
        **payload.model_dump(),
    )

    db.add(work_order)
    db.commit()
    db.refresh(work_order)

    audit.log_event(
        db,
        "work_order",
        work_order.id,
        "created",
        (
            f"Work order opened for {machine.name}: "
            f"{work_order.problem}"
            + (
                f" — assigned to {work_order.assigned_to}"
                if work_order.assigned_to
                else ""
            )
        ),
        performed_by=current.username,
    )

    return work_order


@router.patch(
    "/{wo_id}",
    response_model=schemas.WorkOrderOut,
)
def update_work_order(
    wo_id: int,
    payload: schemas.WorkOrderUpdate,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    work_order = _get_work_order(
        wo_id,
        current,
        db,
    )

    changes = payload.model_dump(
        exclude_unset=True,
    )

    if _is_worker(current):
        # Workers may change status and add resolution notes,
        # but cannot reassign or edit the work definition.
        allowed_fields = {
            "status",
            "resolution_notes",
        }

        unexpected = set(changes) - allowed_fields

        if unexpected:
            raise HTTPException(
                status_code=403,
                detail=(
                    "workers may only update status "
                    "and resolution notes"
                ),
            )

        requested_status = changes.get("status")

        if requested_status:
            valid_statuses = {
                "pending",
                "in_progress",
                "completed",
            }

            if requested_status not in valid_statuses:
                raise HTTPException(
                    status_code=400,
                    detail="invalid work order status",
                )

            current_status = (
                work_order.status.value
            )

            # Enforce the worker workflow.
            if (
                requested_status == "in_progress"
                and current_status != "pending"
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "only pending work orders "
                        "can be acknowledged"
                    ),
                )

            if (
                requested_status == "completed"
                and current_status != "in_progress"
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "a work order must be in progress "
                        "before it can be resolved"
                    ),
                )

    else:
        if "assigned_to" in changes:
            validate_assignee(
                changes["assigned_to"],
                current,
                db,
            )

        # Management clients retain full work-order control.
        if "status" in changes:
            if changes["status"] not in {
                "pending",
                "in_progress",
                "completed",
            }:
                raise HTTPException(
                    status_code=400,
                    detail="invalid work order status",
                )

    for field, value in changes.items():
        setattr(
            work_order,
            field,
            value,
        )

    if payload.status == "completed":
        if not work_order.resolution_notes:
            raise HTTPException(
                status_code=400,
                detail=(
                    "resolution notes are required "
                    "when completing a work order"
                ),
            )

        work_order.completed_at = datetime.utcnow()

        maintenance_record = models.MaintenanceRecord(
            machine_id=work_order.machine_id,
            type=models.MaintenanceType.corrective,
            description=work_order.problem,
            completed_date=work_order.completed_at,
            status=models.MaintenanceStatus.completed,
            performed_by=work_order.assigned_to
            or current.username,
            notes=work_order.resolution_notes,
        )

        db.add(maintenance_record)

    db.commit()
    db.refresh(work_order)

    if payload.status == "completed":
        machine = db.get(
            models.Machine,
            work_order.machine_id,
        )

        audit.log_event(
            db,
            "work_order",
            work_order.id,
            "completed",
            (
                f"Work order resolved for "
                f"{machine.name if machine else work_order.machine_id}: "
                f"{work_order.problem}"
                + (
                    f" — {work_order.resolution_notes}"
                    if work_order.resolution_notes
                    else ""
                )
            ),
            performed_by=(
                work_order.assigned_to
                or current.username
            ),
        )

    elif payload.status == "in_progress":
        audit.log_event(
            db,
            "work_order",
            work_order.id,
            "acknowledged",
            (
                f"Work order #{work_order.id} "
                f"acknowledged by {current.username}"
            ),
            performed_by=current.username,
        )

    return work_order