"""Durable REST command and live-telemetry fallback endpoints for IoT clients."""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models, audit
from ..database import get_db
from ..deps import get_current_user, CurrentUser

router = APIRouter(prefix="/api/devices", tags=["devices"])


def _machine_for_key(db: Session, device_key: str):
    machine = db.query(models.Machine).filter_by(device_key=device_key, iot_enabled=True, archived=False).first()
    if not machine:
        raise HTTPException(401, "invalid or disabled device key")
    return machine


class CommandAckPayload(BaseModel):
    event_id: int


@router.get("/telemetry/latest")
def latest_telemetry(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the latest sensor value for every visible machine/signal."""
    machines = db.query(models.Machine).filter(
        models.Machine.organization_id == current.organization_id,
        models.Machine.archived.is_(False),
    )
    if current.role == models.UserRole.technician.value:
        machines = machines.join(
            models.UserMachineAssignment,
            models.UserMachineAssignment.machine_id == models.Machine.id,
        ).filter(models.UserMachineAssignment.user_id == current.id)
    machine_ids = [row.id for row in machines.all()]
    if not machine_ids:
        return {"machines": []}

    readings = (
        db.query(models.SensorReading)
        .filter(models.SensorReading.machine_id.in_(machine_ids))
        .order_by(
            models.SensorReading.machine_id.asc(),
            models.SensorReading.reading_type.asc(),
            models.SensorReading.recorded_at.desc(),
            models.SensorReading.id.desc(),
        ).all()
    )
    latest = {}
    for reading in readings:
        key = (reading.machine_id, reading.reading_type)
        if key not in latest:
            latest[key] = {
                "machine_id": reading.machine_id,
                "reading_id": reading.id,
                "reading_type": reading.reading_type,
                "value": reading.value,
                "unit": reading.unit,
                "recorded_at": reading.recorded_at,
            }
    return {"machines": list(latest.values())}


@router.get("/commands")
def pending_device_command(x_device_key: str = Header(..., alias="X-Device-Key"), db: Session = Depends(get_db)):
    machine = _machine_for_key(db, x_device_key)
    event = (
        db.query(models.MachineSafetyEvent)
        .filter(
            models.MachineSafetyEvent.machine_id == machine.id,
            models.MachineSafetyEvent.shutdown_requested.is_(True),
            models.MachineSafetyEvent.device_acknowledged.is_(False),
        )
        .order_by(models.MachineSafetyEvent.created_at.asc(), models.MachineSafetyEvent.id.asc())
        .first()
    )
    if not event:
        return {"pending": False, "machine_id": machine.id}
    return {
        "pending": True,
        "command_type": "shutdown_test" if event.event_type == "shutdown_test" else "shutdown",
        "event_id": event.id,
        "machine_id": machine.id,
        "reason": event.message,
        "reading_type": event.reading_type,
        "value": event.value,
        "threshold": event.threshold,
        "created_at": event.created_at,
    }


@router.post("/commands/ack")
def acknowledge_device_command(payload: CommandAckPayload, x_device_key: str = Header(..., alias="X-Device-Key"), db: Session = Depends(get_db)):
    machine = _machine_for_key(db, x_device_key)
    event = db.get(models.MachineSafetyEvent, payload.event_id)
    if not event or event.machine_id != machine.id:
        raise HTTPException(404, "safety command not found for this device")
    event.device_acknowledged = True
    db.commit()
    return {"acknowledged": True, "event_id": event.id, "machine_id": machine.id}


@router.post("/commands/test-shutdown/{machine_id}")
def queue_test_shutdown(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if current.role != models.UserRole.admin.value:
        raise HTTPException(403, "administrator access required")
    machine = db.query(models.Machine).filter(
        models.Machine.id == machine_id,
        models.Machine.organization_id == current.organization_id,
        models.Machine.archived.is_(False),
    ).first()
    if not machine:
        raise HTTPException(404, "machine not found")
    if not machine.iot_enabled or not machine.device_key:
        raise HTTPException(409, "live sensor integration is not enabled")

    event = models.MachineSafetyEvent(
        machine_id=machine.id,
        event_type="shutdown_test",
        reading_type="manual",
        value=0.0,
        threshold=None,
        message="Manual safety shutdown test",
        shutdown_requested=True,
        device_acknowledged=False,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    try:
        audit.log_event(
            db, "machine", machine.id, "safety_shutdown_test",
            f"Manual safety shutdown test queued for {machine.name}",
            organization_id=current.organization_id,
        )
    except Exception:
        db.rollback()
    return {"sent": True, "queued": True, "machine_id": machine.id, "event_id": event.id}
