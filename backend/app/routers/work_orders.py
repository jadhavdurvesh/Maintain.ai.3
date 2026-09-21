from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas, audit
from ..database import get_db
from ..deps import get_current_user, CurrentUser
from ..notification_service import notify_work_order_assigned

router = APIRouter(prefix="/api/work-orders", tags=["work_orders"])


def _is_worker(current: CurrentUser) -> bool:
    return current.id is not None and current.role == models.UserRole.technician.value


def validate_assignee(assigned_to: str | None, current: CurrentUser, db: Session):
    if not assigned_to:
        return
    assignee = db.query(models.User).filter(
        models.User.username == assigned_to,
        models.User.organization_id == current.organization_id,
        models.User.active.is_(True),
    ).first()
    if not assignee:
        raise HTTPException(400, "assigned user not found or inactive")
    if assignee.role == models.UserRole.viewer:
        raise HTTPException(400, "viewers cannot be assigned maintenance work")


def _get_work_order(wo_id: int, current: CurrentUser, db: Session) -> models.WorkOrder:
    work_order = db.query(models.WorkOrder).join(models.Machine).filter(
        models.WorkOrder.id == wo_id,
        models.Machine.organization_id == current.organization_id,
    ).first()
    if not work_order:
        raise HTTPException(404, "work order not found")
    if _is_worker(current) and work_order.assigned_to != current.username:
        raise HTTPException(404, "work order not assigned to this worker")
    return work_order


def _capture_work_order_outcome(db: Session, work_order: models.WorkOrder, current: CurrentUser):
    """Create one initial ML outcome automatically when a work order is completed.

    This is intentionally conservative: a linked fault becomes a confirmed-failure
    training candidate; an unlinked order is recorded as unknown until a technician
    provides stronger evidence in the Fault Log.
    """
    existing = db.query(models.MLOutcomeFeedback).filter_by(work_order_id=work_order.id).first()
    if existing:
        return existing

    outcome_type = "confirmed_failure" if work_order.fault_id else "unknown"
    fault = db.get(models.FaultRecord, work_order.fault_id) if work_order.fault_id else None
    feedback = models.MLOutcomeFeedback(
        machine_id=work_order.machine_id,
        fault_id=work_order.fault_id,
        work_order_id=work_order.id,
        outcome_type=outcome_type,
        corrective_action=work_order.resolution_notes,
        notes="Automatically captured from completed work order; technician can refine the outcome in Fault Log.",
        created_by=current.username,
    )
    db.add(feedback)
    return feedback


@router.get("", response_model=List[schemas.WorkOrderOut])
def list_work_orders(status: str | None = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(models.WorkOrder).join(models.Machine).filter(models.Machine.organization_id == current.organization_id)
    if _is_worker(current):
        query = query.filter(models.WorkOrder.assigned_to == current.username)
    if status:
        query = query.filter(models.WorkOrder.status == status)
    return query.order_by(models.WorkOrder.created_at.desc(), models.WorkOrder.id.desc()).offset(offset).limit(limit).all()


@router.post("", response_model=schemas.WorkOrderOut)
def create_work_order(payload: schemas.WorkOrderIn, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if current.role != models.UserRole.admin.value:
        raise HTTPException(403, "administrator access required")
    if _is_worker(current):
        raise HTTPException(403, "workers cannot create work orders")

    machine = db.get(models.Machine, payload.machine_id)
    if not machine or machine.organization_id != current.organization_id:
        raise HTTPException(404, "machine not found")

    if payload.fault_id:
        fault = db.get(models.FaultRecord, payload.fault_id)
        if not fault or fault.machine_id != machine.id:
            raise HTTPException(400, "fault does not belong to this machine")
        existing = db.query(models.WorkOrder).filter(
            models.WorkOrder.fault_id == fault.id,
            models.WorkOrder.status.in_([models.WorkOrderStatus.pending, models.WorkOrderStatus.in_progress]),
        ).first()
        if existing:
            raise HTTPException(409, f"an active work order already exists (#{existing.id})")

    validate_assignee(payload.assigned_to, current, db)
    work_order = models.WorkOrder(**payload.model_dump())
    db.add(work_order)
    db.commit()
    db.refresh(work_order)

    audit.log_event(
        db, "work_order", work_order.id, "created",
        f"Work order opened for {machine.name}: {work_order.problem}"
        + (f" — assigned to {work_order.assigned_to}" if work_order.assigned_to else ""),
        performed_by=current.username,
    )

    if work_order.assigned_to:
        notify_work_order_assigned(db, work_order, machine)

    return work_order


@router.patch("/{wo_id}", response_model=schemas.WorkOrderOut)
def update_work_order(wo_id: int, payload: schemas.WorkOrderUpdate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    work_order = _get_work_order(wo_id, current, db)
    previous_assignee = work_order.assigned_to
    changes = payload.model_dump(exclude_unset=True)

    if _is_worker(current):
        allowed_fields = {"status", "resolution_notes"}
        unexpected = set(changes) - allowed_fields
        if unexpected:
            raise HTTPException(403, "workers may only update status and resolution notes")
        requested_status = changes.get("status")
        if requested_status:
            if requested_status not in {"pending", "in_progress", "completed"}:
                raise HTTPException(400, "invalid work order status")
            current_status = work_order.status.value
            if requested_status == "in_progress" and current_status != "pending":
                raise HTTPException(400, "only pending work orders can be acknowledged")
            if requested_status == "completed" and current_status != "in_progress":
                raise HTTPException(400, "a work order must be in progress before it can be resolved")
    else:
        if current.role == models.UserRole.viewer.value:
            raise HTTPException(403, "viewers cannot modify work orders")
        if "assigned_to" in changes:
            validate_assignee(changes["assigned_to"], current, db)
        if "status" in changes and changes["status"] not in {"pending", "in_progress", "completed"}:
            raise HTTPException(400, "invalid work order status")

    for field, value in changes.items():
        setattr(work_order, field, value)

    if payload.status == "completed":
        if not work_order.resolution_notes:
            raise HTTPException(400, "resolution notes are required when completing a work order")
        work_order.completed_at = datetime.utcnow()
        _capture_work_order_outcome(db, work_order, current)
        db.add(models.MaintenanceRecord(
            machine_id=work_order.machine_id,
            type=models.MaintenanceType.corrective,
            description=work_order.problem,
            completed_date=work_order.completed_at,
            status=models.MaintenanceStatus.completed,
            performed_by=work_order.assigned_to or current.username,
            notes=work_order.resolution_notes,
        ))

    db.commit()
    db.refresh(work_order)

    if payload.status == "completed":
        machine = db.get(models.Machine, work_order.machine_id)
        audit.log_event(
            db, "work_order", work_order.id, "completed",
            f"Work order resolved for {machine.name if machine else work_order.machine_id}: {work_order.problem}"
            + (f" — {work_order.resolution_notes}" if work_order.resolution_notes else ""),
            performed_by=work_order.assigned_to or current.username,
        )
    elif payload.status == "in_progress":
        audit.log_event(db, "work_order", work_order.id, "acknowledged", f"Work order #{work_order.id} acknowledged by {current.username}", performed_by=current.username)

    if "assigned_to" in changes and work_order.assigned_to and work_order.assigned_to != previous_assignee:
        machine = db.get(models.Machine, work_order.machine_id)
        if machine:
            notify_work_order_assigned(db, work_order, machine)

    return work_order
