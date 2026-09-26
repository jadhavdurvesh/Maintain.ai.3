from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas, audit
from ..database import get_db
from ..deps import get_current_user, CurrentUser
from .runtime import _sync_runtime_from_latest_telemetry

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


def _is_worker(current: CurrentUser) -> bool:
    return current.id is not None and current.role == models.UserRole.technician.value


def _machine_for_user(machine_id: int, current: CurrentUser, db: Session):
    machine = db.query(models.Machine).filter(
        models.Machine.id == machine_id,
        models.Machine.organization_id == current.organization_id,
        models.Machine.archived.is_(False),
    ).first()
    if not machine:
        raise HTTPException(404, "machine not found")
    if _is_worker(current) and not db.query(models.UserMachineAssignment).filter_by(user_id=current.id, machine_id=machine_id).first():
        raise HTTPException(404, "machine not assigned to this worker")
    return machine


@router.get("", response_model=List[schemas.MaintenanceRecordOut])
def list_maintenance(
    machine_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(models.MaintenanceRecord).join(models.Machine).filter(models.Machine.organization_id == current.organization_id)
    if _is_worker(current):
        q = q.join(models.UserMachineAssignment, models.UserMachineAssignment.machine_id == models.MaintenanceRecord.machine_id).filter(models.UserMachineAssignment.user_id == current.id)
    if machine_id:
        q = q.filter(models.MaintenanceRecord.machine_id == machine_id)
    return q.order_by(models.MaintenanceRecord.scheduled_date.desc(), models.MaintenanceRecord.id.desc()).offset(offset).limit(limit).all()


@router.post("/{machine_id}", response_model=schemas.MaintenanceRecordOut)
def schedule_maintenance(
    machine_id: int, payload: schemas.MaintenanceRecordIn,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current.role != models.UserRole.admin.value:
        raise HTTPException(403, "administrator access required")
    machine = _machine_for_user(machine_id, current, db)
    record = models.MaintenanceRecord(machine_id=machine_id, **payload.model_dump())
    db.add(record)
    if payload.scheduled_date:
        machine.next_maintenance_date = payload.scheduled_date
    db.commit()
    db.refresh(record)
    audit.log_event(db, "maintenance", record.id, "scheduled", f"{payload.type.title()} maintenance scheduled for {machine.name}: {payload.description or '—'}", performed_by=current.username)
    return record


@router.post("/{record_id}/complete", response_model=schemas.MaintenanceRecordOut)
def complete_maintenance(
    record_id: int, notes: str = "",
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = db.query(models.MaintenanceRecord).join(models.Machine).filter(models.MaintenanceRecord.id == record_id, models.Machine.organization_id == current.organization_id).first()
    if not record:
        raise HTTPException(404, "maintenance record not found")
    if _is_worker(current) and not db.query(models.UserMachineAssignment).filter_by(user_id=current.id, machine_id=record.machine_id).first():
        raise HTTPException(404, "maintenance record not found")
    machine = db.get(models.Machine, record.machine_id)
    if not machine or machine.archived:
        raise HTTPException(409, "cannot complete maintenance for an archived or missing machine")
    if record.status == models.MaintenanceStatus.completed:
        if notes and notes != (record.notes or ""):
            record.notes = notes
            record.performed_by = current.username
            db.commit()
            db.refresh(record)
        return record
    record.status = models.MaintenanceStatus.completed
    record.completed_date = datetime.utcnow()
    record.performed_by = current.username
    if notes:
        record.notes = notes
    machine.last_maintenance_date = record.completed_date
    machine.health_score = min(100, machine.health_score + 15)
    if machine.health_score >= 70:
        machine.status = models.HealthStatus.healthy
    elif machine.health_score >= 40:
        machine.status = models.HealthStatus.attention
    else:
        machine.status = models.HealthStatus.critical
    db.commit()
    db.refresh(record)
    audit.log_event(db, "maintenance", record.id, "completed", f"Maintenance completed on {machine.name}: {record.description or record.type.value}" + (f" — {notes}" if notes else ""), performed_by=current.username)
    return record


@router.get("/due/upcoming")
def upcoming_and_overdue(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Compute maintenance due from live, telemetry-derived operating hours."""
    machines_query = db.query(models.Machine).filter_by(archived=False, organization_id=current.organization_id)
    if _is_worker(current):
        machines_query = machines_query.join(models.UserMachineAssignment, models.UserMachineAssignment.machine_id == models.Machine.id).filter(models.UserMachineAssignment.user_id == current.id)
    machines = machines_query.all()
    results = []
    for m in machines:
        runtime = _sync_runtime_from_latest_telemetry(db, m)
        current_hours = float(runtime["base_operating_hours"] or 0)
        if runtime["state"] == "running":
            # _sync_runtime_from_latest_telemetry has already settled the row;
            # use its start time to include the current live fraction of an hour.
            started_at = runtime["started_at"]
            if started_at:
                current_hours += max(0.0, (datetime.utcnow() - started_at).total_seconds()) / 3600.0
        interval = float(m.maintenance_interval_hours or 500)
        if interval <= 0:
            interval = 500.0
        hours_since_service = current_hours % interval
        hours_remaining = interval - hours_since_service
        results.append({
            "machine_id": m.id,
            "machine_code": m.machine_code,
            "name": m.name,
            "operating_hours": round(current_hours, 4),
            "interval_hours": interval,
            "hours_remaining": round(hours_remaining, 1),
            "overdue": hours_remaining <= 0,
            "due_soon": 0 < hours_remaining <= interval * 0.1,
            "runtime_state": runtime["state"],
        })
    db.commit()
    return sorted(results, key=lambda r: r["hours_remaining"])
