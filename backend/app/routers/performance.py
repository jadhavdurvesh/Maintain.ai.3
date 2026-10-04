from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user, CurrentUser
from ..performance import period_bounds, telemetry_runtime_hours

router = APIRouter(prefix="/api/machines", tags=["machine-performance"])

def _machine(db, machine_id, current):
    machine = db.query(models.Machine).filter(
        models.Machine.id == machine_id,
        models.Machine.organization_id == current.organization_id,
        models.Machine.archived.is_(False),
    ).first()
    if not machine:
        raise HTTPException(404, "machine not found")
    if current.role == models.UserRole.technician.value:
        ok = db.query(models.UserMachineAssignment).filter_by(user_id=current.id, machine_id=machine_id).first()
        if not ok:
            raise HTTPException(404, "machine not found")
    return machine

def _failure_metrics(db, machine_id, start, end):
    faults = db.query(models.FaultRecord).filter(
        models.FaultRecord.machine_id == machine_id,
        models.FaultRecord.resolved_date.isnot(None),
        models.FaultRecord.resolved_date >= start,
        models.FaultRecord.resolved_date < end,
    ).all()
    durations = []
    for fault in faults:
        if fault.reported_date and fault.resolved_date:
            minutes = (fault.resolved_date - fault.reported_date).total_seconds() / 60
            if minutes >= 0:
                durations.append(minutes)
    return len(faults), (sum(durations) / len(durations) if durations else None)

def _payload(machine, profile, monthly, month, db):
    start, end = period_bounds(month)
    auto_runtime = telemetry_runtime_hours(db, machine.id, start, end)
    runtime = (monthly.manual_current_working_hours if monthly and monthly.manual_current_working_hours is not None else (auto_runtime if auto_runtime is not None else (monthly.manual_runtime_hours if monthly else None)))
    planned = monthly.planned_hours if monthly else None
    failures, calculated_mttr = _failure_metrics(db, machine.id, start, end)
    calculated_mtbf = (runtime / failures) if runtime is not None and failures else None
    calculated_availability = (runtime / planned * 100) if runtime is not None and planned and planned > 0 else None
    mtbf = monthly.manual_mtbf_hours if monthly and monthly.manual_mtbf_hours is not None else calculated_mtbf
    mttr = monthly.manual_mttr_minutes if monthly and monthly.manual_mttr_minutes is not None else calculated_mttr
    availability = monthly.manual_availability_percent if monthly and monthly.manual_availability_percent is not None else calculated_availability
    total = monthly.total_units if monthly else None
    good = monthly.good_units if monthly else None
    rejected = monthly.rejected_units if monthly else None
    ideal = monthly.ideal_cycle_seconds if monthly else None
    performance = None
    quality = None
    oee = None
    if runtime and runtime > 0 and total is not None and ideal is not None and ideal > 0:
        performance = min(100.0, ideal * total / (runtime * 3600) * 100)
    if total is not None and total > 0 and good is not None:
        quality = min(100.0, good / total * 100)
    calculated_performance = performance
    calculated_quality = quality
    calculated_oee = availability * performance * quality / 10000 if availability is not None and performance is not None and quality is not None else None
    performance = monthly.manual_performance_percent if monthly and monthly.manual_performance_percent is not None else calculated_performance
    quality = monthly.manual_quality_percent if monthly and monthly.manual_quality_percent is not None else calculated_quality
    oee = monthly.manual_oee_percent if monthly and monthly.manual_oee_percent is not None else calculated_oee
    return {
        "machine_id": machine.id, "machine_name": machine.name, "month": month,
        "started_on": profile.started_on if profile else None,
        "capacity": profile.rated_capacity if profile else None,
        "capacity_unit": profile.capacity_unit if profile else None,
        "oee_target": profile.oee_target if profile else None,
        "current_working_hours": float(machine.operating_hours or 0),
        "period_working_hours": runtime,
        "runtime_source": "manual_override" if monthly and monthly.manual_current_working_hours is not None else ("telemetry" if auto_runtime is not None else ("manual" if runtime is not None else None)),
        "planned_hours": planned, "failures": failures, "mtbf_hours": mtbf,
        "mttr_minutes": mttr, "availability_percent": min(100.0, availability) if availability is not None else None,
        "total_units": total, "good_units": good, "rejected_units": rejected,
        "ideal_cycle_seconds": ideal, "performance_percent": performance,
        "quality_percent": quality, "oee_percent": oee,
        "profile": schemas.MachinePerformanceProfileOut.model_validate(profile).model_dump() if profile else None,
        "monthly": schemas.MachinePerformanceMonthOut.model_validate(monthly).model_dump() if monthly else None,
    }

@router.get("/{machine_id}/performance")
def get_performance(machine_id: int, month: str = Query(..., pattern=r"^\d{4}-\d{2}$"), current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    machine = _machine(db, machine_id, current)
    profile = db.query(models.MachinePerformanceProfile).filter_by(machine_id=machine.id).first()
    monthly = db.query(models.MachinePerformanceMonth).filter_by(machine_id=machine.id, month=month).first()
    return _payload(machine, profile, monthly, month, db)

@router.put("/{machine_id}/performance/profile", response_model=schemas.MachinePerformanceProfileOut)
def save_profile(machine_id: int, payload: schemas.MachinePerformanceProfileIn, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if current.role != models.UserRole.admin.value:
        raise HTTPException(403, "administrator access required")
    machine = _machine(db, machine_id, current)
    profile = db.query(models.MachinePerformanceProfile).filter_by(machine_id=machine.id).first()
    if not profile:
        profile = models.MachinePerformanceProfile(machine_id=machine.id)
        db.add(profile)
    for field, value in payload.model_dump().items():
        setattr(profile, field, value)
    db.commit(); db.refresh(profile)
    return profile

@router.put("/{machine_id}/performance/month", response_model=schemas.MachinePerformanceMonthOut)
def save_month(machine_id: int, payload: schemas.MachinePerformanceMonthIn, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if current.role != models.UserRole.admin.value:
        raise HTTPException(403, "administrator access required")
    _machine(db, machine_id, current)
    monthly = db.query(models.MachinePerformanceMonth).filter_by(machine_id=machine_id, month=payload.month).first()
    if not monthly:
        monthly = models.MachinePerformanceMonth(machine_id=machine_id, month=payload.month)
        db.add(monthly)
    for field, value in payload.model_dump().items():
        setattr(monthly, field, value)
    db.commit(); db.refresh(monthly)
    return monthly
