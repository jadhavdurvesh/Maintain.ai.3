"""REST command bridge for device clients that cannot hold a WebSocket.

The primary telemetry path is HTTPS ingestion + Supabase Realtime. Safety
commands are persisted in the existing machine_safety_events table so a
serverless deployment or a reconnecting gateway cannot lose a shutdown.
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models, audit
from ..database import get_db
from ..deps import get_current_user, CurrentUser

router = APIRouter(prefix="/api/devices", tags=["devices"])


def _machine_for_key(db: Session, device_key: str):
    machine = (
        db.query(models.Machine)
        .filter_by(device_key=device_key, iot_enabled=True, archived=False)
        .first()
    )
    if not machine:
        raise HTTPException(401, "invalid or disabled device key")
    return machine


class CommandAckPayload(BaseModel):
    event_id: int


@router.get("/commands")
def pending_device_command(
    x_device_key: str = Header(..., alias="X-Device-Key"),
    db: Session = Depends(get_db),
):
    """Return the oldest unacknowledged shutdown command for this device.

    This endpoint is intentionally idempotent: polling the same command before
    acknowledgement returns the same event instead of creating duplicates.
    """
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

    command_type = "shutdown_test" if event.event_type == "shutdown_test" else "shutdown"
    return {
        "pending": True,
        "command_type": command_type,
        "event_id": event.id,
        "machine_id": machine.id,
        "reason": event.message,
        "reading_type": event.reading_type,
        "value": event.value,
        "threshold": event.threshold,
        "created_at": event.created_at,
    }


@router.post("/commands/ack")
def acknowledge_device_command(
    payload: CommandAckPayload,
    x_device_key: str = Header(..., alias="X-Device-Key"),
    db: Session = Depends(get_db),
):
    machine = _machine_for_key(db, x_device_key)
    event = db.get(models.MachineSafetyEvent, payload.event_id)
    if not event or event.machine_id != machine.id:
        raise HTTPException(404, "safety command not found for this device")
    event.device_acknowledged = True
    db.commit()
    return {"acknowledged": True, "event_id": event.id, "machine_id": machine.id}


@router.post("/{machine_id}/safety/test-shutdown")
def test_shutdown_command(
    machine_id: int,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Persist a safety test command so both WebSocket and REST devices receive it."""
    if current.role != models.UserRole.admin.value:
        raise HTTPException(403, "administrator access required")
    machine = (
        db.query(models.Machine)
        .filter(
            models.Machine.id == machine_id,
            models.Machine.organization_id == current.organization_id,
            models.Machine.archived.is_(False),
        )
        .first()
    )
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

    audit.log_event(
        db,
        "machine",
        machine.id,
        "safety_shutdown_test",
        f"Manual safety shutdown test queued for {machine.name}",
        organization_id=current.organization_id,
    )

    # If the legacy long-lived device WebSocket is present in this process,
    # deliver immediately too. REST clients will receive the same durable event
    # through /api/devices/commands.
    try:
        from .devices import _device_command_clients
        client = _device_command_clients.get(machine.id)
        if client:
            import asyncio
            asyncio.create_task(client.send_json({
                "type": "shutdown_test",
                "machine_id": machine.id,
                "reason": event.message,
                "reading_type": event.reading_type,
                "value": event.value,
                "threshold": event.threshold,
                "event_id": event.id,
            }))
    except Exception:
        pass

    return {"sent": True, "queued": True, "machine_id": machine.id, "event_id": event.id}
