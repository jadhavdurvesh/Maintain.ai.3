"""Durable REST command and live-telemetry fallback endpoints for IoT clients."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models, audit
from ..database import get_db
from ..deps import get_current_user, CurrentUser

router = APIRouter(prefix="/api/devices", tags=["devices"])

_READING_TYPE_ALIASES = {"motor_current": "current", "motor-current": "current", "machine_load": "load", "machine-load": "load"}

def _normalize_reading_type(value: str | None) -> str:
    key = (value or "").strip().lower()
    return _READING_TYPE_ALIASES.get(key, key)

def _machine_for_key(db: Session, device_key: str):
    machine = db.query(models.Machine).filter_by(device_key=device_key, iot_enabled=True, archived=False).first()
    if not machine: raise HTTPException(401, "invalid or disabled device key")
    return machine

class CommandAckPayload(BaseModel):
    event_id: int

class SafetyPolicyPayload(BaseModel):
    enabled: bool = False
    monitored_reading_type: str = "temperature"
    unit: str | None = None
    warning_low: float | None = None
    warning_high: float | None = None
    shutdown_low: float | None = None
    shutdown_high: float | None = None
    auto_shutdown_enabled: bool = False

def _threshold_trip_for_latest_reading(db: Session, machine: models.Machine):
    cutoff = datetime.utcnow() - timedelta(seconds=30)
    readings = db.query(models.SensorReading).filter(models.SensorReading.machine_id == machine.id, models.SensorReading.recorded_at >= cutoff).order_by(models.SensorReading.recorded_at.desc(), models.SensorReading.id.desc()).limit(32).all()
    latest = {}
    for reading in readings:
        kind = _normalize_reading_type(reading.reading_type)
        if kind and kind not in latest: latest[kind] = reading
    if not latest: return None
    policies = db.query(models.MachineSafetyPolicy).filter_by(machine_id=machine.id, enabled=True, auto_shutdown_enabled=True).all()
    policy_by_type = {_normalize_reading_type(p.monitored_reading_type): p for p in policies}
    for reading_type, reading in latest.items():
        policy = policy_by_type.get(reading_type)
        if not policy: continue
        value = float(reading.value)
        low_trip = policy.shutdown_low is not None and value <= float(policy.shutdown_low)
        high_trip = policy.shutdown_high is not None and value >= float(policy.shutdown_high)
        if not (low_trip or high_trip): continue
        threshold = float(policy.shutdown_low if low_trip else policy.shutdown_high)
        direction = "below" if low_trip else "above"
        message = f"{machine.name}: {reading_type} is {direction} the configured shutdown threshold ({value:g}{reading.unit or policy.unit or ''}; limit {threshold:g}{reading.unit or policy.unit or ''})."
        pending = db.query(models.MachineSafetyEvent).filter(models.MachineSafetyEvent.machine_id == machine.id, models.MachineSafetyEvent.event_type == "shutdown_threshold", models.MachineSafetyEvent.reading_type == reading_type, models.MachineSafetyEvent.shutdown_requested.is_(True), models.MachineSafetyEvent.device_acknowledged.is_(False)).order_by(models.MachineSafetyEvent.created_at.desc()).first()
        if pending: return pending
        recent = db.query(models.MachineSafetyEvent).filter(models.MachineSafetyEvent.machine_id == machine.id, models.MachineSafetyEvent.event_type == "shutdown_threshold", models.MachineSafetyEvent.reading_type == reading_type, models.MachineSafetyEvent.created_at >= datetime.utcnow() - timedelta(minutes=5)).order_by(models.MachineSafetyEvent.created_at.desc()).first()
        if recent: continue
        event = models.MachineSafetyEvent(machine_id=machine.id, event_type="shutdown_threshold", reading_type=reading_type, value=value, threshold=threshold, message=message, shutdown_requested=True, device_acknowledged=False)
        db.add(event); policy.last_trip_at = datetime.utcnow(); policy.last_trip_value = value; policy.last_trip_reason = message; db.commit(); db.refresh(event)
        return event
    return None

@router.get("/telemetry/latest")
def latest_telemetry(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    machines = db.query(models.Machine).filter(models.Machine.organization_id == current.organization_id, models.Machine.archived.is_(False))
    if current.role == models.UserRole.technician.value:
        machines = machines.join(models.UserMachineAssignment, models.UserMachineAssignment.machine_id == models.Machine.id).filter(models.UserMachineAssignment.user_id == current.id)
    machine_ids = [row.id for row in machines.all()]
    if not machine_ids: return {"machines": []}
    cutoff = datetime.utcnow() - timedelta(minutes=2)
    readings = db.query(models.SensorReading).filter(models.SensorReading.machine_id.in_(machine_ids), models.SensorReading.recorded_at >= cutoff).order_by(models.SensorReading.machine_id.asc(), models.SensorReading.reading_type.asc(), models.SensorReading.recorded_at.desc(), models.SensorReading.id.desc()).all()
    latest = {}
    for reading in readings:
        key = (reading.machine_id, reading.reading_type)
        if key not in latest: latest[key] = {"machine_id": reading.machine_id, "reading_id": reading.id, "reading_type": reading.reading_type, "value": reading.value, "unit": reading.unit, "recorded_at": reading.recorded_at}
    return {"machines": list(latest.values())}

@router.get("/commands")
def pending_device_command(x_device_key: str = Header(..., alias="X-Device-Key"), db: Session = Depends(get_db)):
    machine = _machine_for_key(db, x_device_key); event = _threshold_trip_for_latest_reading(db, machine)
    if not event: event = db.query(models.MachineSafetyEvent).filter(models.MachineSafetyEvent.machine_id == machine.id, models.MachineSafetyEvent.shutdown_requested.is_(True), models.MachineSafetyEvent.device_acknowledged.is_(False)).order_by(models.MachineSafetyEvent.created_at.asc(), models.MachineSafetyEvent.id.asc()).first()
    if not event: return {"pending": False, "machine_id": machine.id}
    return {"pending": True, "command_type": "shutdown_test" if event.event_type == "shutdown_test" else "shutdown", "event_id": event.id, "machine_id": machine.id, "reason": event.message, "reading_type": event.reading_type, "value": event.value, "threshold": event.threshold, "created_at": event.created_at}

@router.post("/commands/ack")
def acknowledge_device_command(payload: CommandAckPayload, x_device_key: str = Header(..., alias="X-Device-Key"), db: Session = Depends(get_db)):
    machine = _machine_for_key(db, x_device_key); event = db.get(models.MachineSafetyEvent, payload.event_id)
    if not event or event.machine_id != machine.id: raise HTTPException(404, "safety command not found for this device")
    event.device_acknowledged = True; db.commit(); return {"acknowledged": True, "event_id": event.id, "machine_id": machine.id}

@router.get("/{machine_id}/safety")
def get_machine_safety(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    machine = db.query(models.Machine).filter(models.Machine.id == machine_id, models.Machine.organization_id == current.organization_id, models.Machine.archived.is_(False)).first()
    if not machine: raise HTTPException(404, "machine not found")
    if current.role == models.UserRole.technician.value and not db.query(models.UserMachineAssignment).filter_by(user_id=current.id, machine_id=machine_id).first(): raise HTTPException(404, "machine not assigned to this worker")
    policies = db.query(models.MachineSafetyPolicy).filter_by(machine_id=machine.id).order_by(models.MachineSafetyPolicy.id.asc()).all()
    rows = [{c.name: getattr(p, c.name) for c in models.MachineSafetyPolicy.__table__.columns if c.name not in {"id", "machine_id"}} for p in policies]
    return {"configured": bool(rows), "enabled": any(bool(r.get("enabled")) for r in rows), "policies": rows, "auto_shutdown_enabled": any(bool(r.get("auto_shutdown_enabled")) for r in rows)}

@router.put("/{machine_id}/safety")
def save_machine_safety(machine_id: int, payload: SafetyPolicyPayload, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if current.role != models.UserRole.admin.value: raise HTTPException(403, "administrator access required")
    machine = db.query(models.Machine).filter(models.Machine.id == machine_id, models.Machine.organization_id == current.organization_id, models.Machine.archived.is_(False)).first()
    if not machine: raise HTTPException(404, "machine not found")
    signal = _normalize_reading_type(payload.monitored_reading_type)
    if not signal: raise HTTPException(400, "A monitored safety signal is required.")
    if payload.auto_shutdown_enabled and not payload.enabled: raise HTTPException(400, "Enable threshold monitoring before enabling automatic shutdown.")
    if payload.shutdown_low is not None and payload.warning_low is not None and payload.warning_low < payload.shutdown_low: raise HTTPException(400, "Low warning threshold must be reached before the low shutdown threshold.")
    if payload.shutdown_high is not None and payload.warning_high is not None and payload.warning_high > payload.shutdown_high: raise HTTPException(400, "High warning threshold must be reached before the high shutdown threshold.")
    if payload.shutdown_low is not None and payload.shutdown_high is not None and payload.shutdown_low >= payload.shutdown_high: raise HTTPException(400, "Low shutdown threshold must be below high shutdown threshold.")
    policy = db.query(models.MachineSafetyPolicy).filter_by(machine_id=machine.id, monitored_reading_type=signal).order_by(models.MachineSafetyPolicy.id.asc()).first()
    if policy is None: policy = models.MachineSafetyPolicy(machine_id=machine.id, monitored_reading_type=signal); db.add(policy)
    values = payload.model_dump(); values["monitored_reading_type"] = signal
    for key, value in values.items(): setattr(policy, key, value)
    policy.updated_at = datetime.utcnow(); db.commit(); db.refresh(policy)
    try: audit.log_event(db, "machine", machine.id, "safety_policy_updated", f"Safety thresholds updated for {machine.name} ({signal})", organization_id=current.organization_id)
    except Exception: db.rollback()
    policies = db.query(models.MachineSafetyPolicy).filter_by(machine_id=machine.id).order_by(models.MachineSafetyPolicy.id.asc()).all()
    rows = [{c.name: getattr(p, c.name) for c in models.MachineSafetyPolicy.__table__.columns if c.name not in {"id", "machine_id"}} for p in policies]
    saved = next(r for r in rows if r.get("monitored_reading_type") == signal)
    return {"configured": True, "policies": rows, **saved}

@router.post("/{machine_id}/safety/test-shutdown")
def queue_test_shutdown(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if current.role != models.UserRole.admin.value: raise HTTPException(403, "administrator access required")
    machine = db.query(models.Machine).filter(models.Machine.id == machine_id, models.Machine.organization_id == current.organization_id, models.Machine.archived.is_(False)).first()
    if not machine: raise HTTPException(404, "machine not found")
    if not machine.iot_enabled or not machine.device_key: raise HTTPException(409, "live sensor integration is not enabled")
    event = models.MachineSafetyEvent(machine_id=machine.id, event_type="shutdown_test", reading_type="manual", value=0.0, threshold=None, message="Manual safety shutdown test", shutdown_requested=True, device_acknowledged=False)
    db.add(event); db.commit(); db.refresh(event)
    try: audit.log_event(db, "machine", machine.id, "safety_shutdown_test", f"Manual safety shutdown test queued for {machine.name}", organization_id=current.organization_id)
    except Exception: db.rollback()
    return {"sent": True, "queued": True, "machine_id": machine.id, "event_id": event.id}
