from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, audit
from ..database import get_db
from ..deps import get_current_user, CurrentUser

router = APIRouter(prefix="/api/work-orders", tags=["work_orders"])


@router.get("", response_model=List[schemas.WorkOrderOut])
def list_work_orders(
    status: str | None = None,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # WorkOrder has no organization_id of its own — it inherits scope from
    # its machine, so a join keeps that single source of truth rather than
    # duplicating organization_id onto every child table.
    q = (
        db.query(models.WorkOrder)
        .join(models.Machine)
        .filter(models.Machine.organization_id == current.organization_id)
    )
    if status:
        q = q.filter(models.WorkOrder.status == status)
    return q.order_by(models.WorkOrder.created_at.desc()).all()


@router.post("", response_model=schemas.WorkOrderOut)
def create_work_order(
    payload: schemas.WorkOrderIn,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    machine = db.get(models.Machine, payload.machine_id)
    if not machine or machine.organization_id != current.organization_id:
        raise HTTPException(404, "machine not found")
    wo = models.WorkOrder(**payload.model_dump())
    db.add(wo)
    db.commit()
    db.refresh(wo)
    audit.log_event(db, "work_order", wo.id, "created", f"Work order opened for {machine.name}: {wo.problem}")
    return wo


@router.patch("/{wo_id}", response_model=schemas.WorkOrderOut)
def update_work_order(
    wo_id: int, payload: schemas.WorkOrderUpdate,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wo = db.get(models.WorkOrder, wo_id)
    if not wo or wo.machine.organization_id != current.organization_id:
        raise HTTPException(404, "work order not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(wo, field, value)
    if payload.status == "completed":
        wo.completed_at = datetime.utcnow()
        # completed work automatically becomes maintenance history — this
        # MaintenanceRecord is never deleted even if the work order itself
        # is later modified again.
        record = models.MaintenanceRecord(
            machine_id=wo.machine_id,
            type=models.MaintenanceType.corrective,
            description=wo.problem,
            completed_date=wo.completed_at,
            status=models.MaintenanceStatus.completed,
            performed_by=wo.assigned_to,
            notes=wo.resolution_notes,
        )
        db.add(record)
        db.commit()
        machine = db.get(models.Machine, wo.machine_id)
        audit.log_event(
            db, "work_order", wo.id, "completed",
            f"Work order resolved for {machine.name if machine else wo.machine_id}: {wo.problem}"
            + (f" — {wo.resolution_notes}" if wo.resolution_notes else ""),
            performed_by=wo.assigned_to,
        )
    db.commit()
    db.refresh(wo)
    return wo
