from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, audit
from ..database import get_db
from ..deps import get_current_user, CurrentUser

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


@router.get("", response_model=List[schemas.MaintenanceRecordOut])
def list_maintenance(
    machine_id: int | None = None,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (
        db.query(models.MaintenanceRecord)
        .join(models.Machine)
        .filter(models.Machine.organization_id == current.organization_id)
    )
    if machine_id:
        q = q.filter(models.MaintenanceRecord.machine_id == machine_id)
    return q.order_by(models.MaintenanceRecord.scheduled_date.asc()).all()


@router.post("/{machine_id}", response_model=schemas.MaintenanceRecordOut)
def schedule_maintenance(
    machine_id: int, payload: schemas.MaintenanceRecordIn,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    machine = db.get(models.Machine, machine_id)
    if not machine or machine.organization_id != current.organization_id:
        raise HTTPException(404, "machine not found")
    record = models.MaintenanceRecord(machine_id=machine_id, **payload.model_dump())
    db.add(record)

    if payload.scheduled_date:
        machine.next_maintenance_date = payload.scheduled_date
    db.commit()
    db.refresh(record)
    audit.log_event(db, "maintenance", record.id, "scheduled", f"{payload.type.title()} maintenance scheduled for {machine.name}: {payload.description or '—'}")
    return record


@router.post("/{record_id}/complete", response_model=schemas.MaintenanceRecordOut)
def complete_maintenance(
    record_id: int, notes: str = "",
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = db.get(models.MaintenanceRecord, record_id)
    if not record or record.machine.organization_id != current.organization_id:
        raise HTTPException(404, "maintenance record not found")
    record.status = models.MaintenanceStatus.completed
    record.completed_date = datetime.utcnow()
    if notes:
        record.notes = notes

    machine = db.get(models.Machine, record.machine_id)
    if machine:
        machine.last_maintenance_date = record.completed_date
        # bump health score back up on completed preventive/corrective work
        machine.health_score = min(100, machine.health_score + 15)
        if machine.health_score >= 70:
            machine.status = models.HealthStatus.healthy
        elif machine.health_score >= 40:
            machine.status = models.HealthStatus.attention
        else:
            machine.status = models.HealthStatus.critical

    db.commit()
    db.refresh(record)
    audit.log_event(
        db, "maintenance", record.id, "completed",
        f"Maintenance completed on {machine.name if machine else record.machine_id}: {record.description or record.type.value}"
        + (f" — {notes}" if notes else ""),
        performed_by=record.performed_by,
    )
    return record


@router.get("/due/upcoming")
def upcoming_and_overdue(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Computes due-soon / overdue maintenance from operating hours, per the spec's
    'Smart Maintenance Scheduler': next service = interval - (current_hours mod interval)."""
    machines = db.query(models.Machine).filter_by(archived=False, organization_id=current.organization_id).all()
    results = []
    for m in machines:
        interval = m.maintenance_interval_hours or 500
        hours_since_service = m.operating_hours % interval
        hours_remaining = interval - hours_since_service
        results.append({
            "machine_id": m.id,
            "machine_code": m.machine_code,
            "name": m.name,
            "operating_hours": m.operating_hours,
            "interval_hours": interval,
            "hours_remaining": round(hours_remaining, 1),
            "overdue": hours_remaining <= 0,
            "due_soon": 0 < hours_remaining <= interval * 0.1,
        })
    return sorted(results, key=lambda r: r["hours_remaining"])
