from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, audit
from ..database import get_db
from ..deps import get_current_user, CurrentUser
from ..alerts_engine import evaluate_machine

router = APIRouter(prefix="/api/faults", tags=["faults"])


@router.get("", response_model=List[schemas.FaultRecordOut])
def list_faults(
    machine_id: int | None = None,
    unresolved_only: bool = False,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (
        db.query(models.FaultRecord)
        .join(models.Machine)
        .filter(models.Machine.organization_id == current.organization_id)
    )
    if machine_id is not None:
        q = q.filter(models.FaultRecord.machine_id == machine_id)
    if unresolved_only:
        q = q.filter(models.FaultRecord.resolved_date.is_(None))
    return q.order_by(models.FaultRecord.reported_date.desc()).all()


@router.post("", response_model=schemas.FaultRecordOut)
def create_fault(
    payload: schemas.FaultRecordIn,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    machine = db.get(models.Machine, payload.machine_id)
    if not machine or machine.organization_id != current.organization_id:
        raise HTTPException(404, "machine not found")
    fault = models.FaultRecord(**payload.model_dump())
    db.add(fault)
    db.commit()
    db.refresh(fault)
    audit.log_event(
        db, "fault", fault.id, "reported",
        f"Fault reported for {machine.name}: {fault.description}",
    )
    evaluate_machine(db, machine)
    return fault


@router.post("/{fault_id}/resolve", response_model=schemas.FaultRecordOut)
def resolve_fault(
    fault_id: int,
    payload: schemas.FaultResolveIn,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    fault = db.get(models.FaultRecord, fault_id)
    if not fault or fault.machine.organization_id != current.organization_id:
        raise HTTPException(404, "fault not found")
    if fault.resolved_date is not None:
        raise HTTPException(409, "fault is already resolved")

    if payload.cause:
        fault.cause = payload.cause
    fault.resolution = payload.resolution
    fault.resolved_date = datetime.utcnow()
    db.commit()
    db.refresh(fault)

    audit.log_event(
        db, "fault", fault.id, "resolved",
        f"Fault resolved for {fault.machine.name}: {fault.resolution}",
    )
    return fault


@router.post("/{fault_id}/work-order", response_model=schemas.WorkOrderOut)
def create_work_order_from_fault(
    fault_id: int,
    payload: schemas.WorkOrderIn | None = None,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    fault = db.get(models.FaultRecord, fault_id)
    if not fault or fault.machine.organization_id != current.organization_id:
        raise HTTPException(404, "fault not found")

    # A fault represents one underlying maintenance issue. Do not create a new
    # pending/in-progress work order every time the button is clicked.
    existing = (
        db.query(models.WorkOrder)
        .filter(
            models.WorkOrder.machine_id == fault.machine_id,
            models.WorkOrder.problem == fault.description,
            models.WorkOrder.status.in_([
                models.WorkOrderStatus.pending,
                models.WorkOrderStatus.in_progress,
            ]),
        )
        .order_by(models.WorkOrder.created_at.desc())
        .first()
    )
    if existing is not None:
        raise HTTPException(409, f"an active work order already exists (#{existing.id})")

    priority = fault.severity.value if hasattr(fault.severity, "value") else str(fault.severity)
    if priority == "warning":
        priority = "medium"
    if priority not in {"low", "medium", "high", "critical"}:
        priority = "medium"

    data = payload.model_dump() if payload else {}
    data["machine_id"] = fault.machine_id
    data["problem"] = data.get("problem") or fault.description
    data["priority"] = data.get("priority") or priority
    data["recommended_actions"] = data.get("recommended_actions") or (
        f"Investigate fault: {fault.symptoms}" if fault.symptoms else "Investigate reported fault and confirm root cause."
    )

    assigned_to = data.get("assigned_to")
    if assigned_to:
        assignee = (
            db.query(models.User)
            .filter(
                models.User.username == assigned_to,
                models.User.organization_id == current.organization_id,
            )
            .first()
        )
        if not assignee:
            raise HTTPException(400, "assigned user not found in this organization")
        if assignee.role == models.UserRole.viewer:
            raise HTTPException(400, "viewers cannot be assigned maintenance work")

    wo = models.WorkOrder(**data)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    audit.log_event(
        db,
        "fault",
        fault.id,
        "work_order_created",
        f"Work order #{wo.id} created from fault #{fault.id}"
        + (f" and assigned to {wo.assigned_to}" if wo.assigned_to else ""),
        performed_by=current.username,
    )
    return wo
