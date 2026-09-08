"""
Optional live-sensor integration. A machine works with pure manual entry
forever if nobody touches this — iot_enabled defaults to False and the
ingest endpoint refuses readings until a device key exists AND the machine
has been explicitly switched on.

This is intentionally a separate, minimal auth path (a per-machine key in
a header) rather than requiring a full user login, since an ESP32 has no
browser session to log in with. The key is scoped to exactly one machine
and can be regenerated (invalidating the old one) at any time.
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models, audit
from ..database import get_db
from ..alerts_engine import evaluate_machine

router = APIRouter(prefix="/api/devices", tags=["devices"])


def _check_sensor_anomaly(db: Session, machine: models.Machine, reading: models.SensorReading):
    """No per-machine thresholds to configure — instead, compares this
    reading to the machine's own recent baseline for the same sensor type.
    Needs a small amount of history before it says anything, same
    philosophy as the offline diagnostic engine: no confident claim
    without enough signal to back it up."""
    recent = (
        db.query(models.SensorReading)
        .filter_by(machine_id=machine.id, reading_type=reading.reading_type)
        .filter(models.SensorReading.id != reading.id)
        .order_by(models.SensorReading.recorded_at.desc())
        .limit(10)
        .all()
    )
    if len(recent) < 3:
        return
    baseline = sum(r.value for r in recent) / len(recent)
    if baseline > 0 and reading.value > baseline * 1.5:
        exists = (
            db.query(models.Alert)
            .filter_by(machine_id=machine.id, alert_type=f"sensor_anomaly_{reading.reading_type}", resolved=False)
            .first()
        )
        if not exists:
            db.add(models.Alert(
                machine_id=machine.id,
                alert_type=f"sensor_anomaly_{reading.reading_type}",
                severity=models.AlertSeverity.warning,
                message=(
                    f"{machine.name}: live {reading.reading_type} reading ({reading.value}{reading.unit or ''}) "
                    f"is well above its recent baseline (~{round(baseline, 1)}{reading.unit or ''})."
                ),
            ))
            db.commit()


class DeviceStatusOut(BaseModel):
    iot_enabled: bool
    has_key: bool
    device_key: str | None = None  # only ever returned once, right after (re)generation


class IngestPayload(BaseModel):
    reading_type: str
    value: float
    unit: str | None = None


@router.get("/{machine_id}/status", response_model=DeviceStatusOut)
def device_status(machine_id: int, db: Session = Depends(get_db)):
    machine = db.get(models.Machine, machine_id)
    if not machine:
        raise HTTPException(404, "machine not found")
    return DeviceStatusOut(iot_enabled=machine.iot_enabled, has_key=bool(machine.device_key))


@router.post("/{machine_id}/enable", response_model=DeviceStatusOut)
def enable_device(machine_id: int, db: Session = Depends(get_db)):
    """Turns on IoT ingestion for this machine and issues a fresh device key.
    Calling this again rotates the key — the old one stops working immediately."""
    machine = db.get(models.Machine, machine_id)
    if not machine:
        raise HTTPException(404, "machine not found")
    machine.iot_enabled = True
    machine.device_key = secrets.token_hex(16)
    db.commit()
    audit.log_event(db, "machine", machine.id, "iot_enabled", f"Live sensor integration enabled for {machine.name}")
    return DeviceStatusOut(iot_enabled=True, has_key=True, device_key=machine.device_key)


@router.post("/{machine_id}/disable", response_model=DeviceStatusOut)
def disable_device(machine_id: int, db: Session = Depends(get_db)):
    """Turns IoT ingestion back off. The key is kept (not deleted) so
    re-enabling later doesn't silently reuse an old, possibly-leaked key —
    enabling again always issues a brand new one."""
    machine = db.get(models.Machine, machine_id)
    if not machine:
        raise HTTPException(404, "machine not found")
    machine.iot_enabled = False
    db.commit()
    audit.log_event(db, "machine", machine.id, "iot_disabled", f"Live sensor integration disabled for {machine.name}")
    return DeviceStatusOut(iot_enabled=False, has_key=bool(machine.device_key))


@router.post("/ingest")
def ingest_reading(
    payload: IngestPayload,
    x_device_key: str = Header(..., alias="X-Device-Key"),
    db: Session = Depends(get_db),
):
    """What an ESP32 (or any device) actually calls — see firmware/esp32_example.ino."""
    machine = db.query(models.Machine).filter_by(device_key=x_device_key).first()
    if not machine or not machine.iot_enabled:
        # Same error either way — doesn't reveal whether the key almost matched something
        raise HTTPException(401, "invalid or disabled device key")

    reading = models.SensorReading(
        machine_id=machine.id,
        reading_type=payload.reading_type,
        value=payload.value,
        unit=payload.unit,
        source="sensor",
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)

    # Live data can move fast — recompute alerts right away instead of
    # waiting for the next manual check, same engine manual entries use,
    # plus a baseline check specific to this live reading.
    evaluate_machine(db, machine)
    _check_sensor_anomaly(db, machine, reading)

    return {"accepted": True, "machine": machine.name, "recorded_at": reading.recorded_at}
