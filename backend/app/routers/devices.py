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
    """Compare this reading with the machine's own recent baseline."""
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


def _reading_condition_score(db: Session, machine: models.Machine, reading_type: str, value: float) -> float:
    """Turn a live sensor into a simple 0-100 condition score.

    This is a transparent engineering heuristic, not the ML model. It is
    deliberately conservative so the UI health score visibly reacts to live
    sensor stress while the learned RandomForest remains responsible for
    predictive-risk analysis elsewhere in the application.
    """
    kind = (reading_type or "").lower()

    if kind == "temperature":
        if value <= 45:
            return 100.0
        if value <= 60:
            return 100.0 - (value - 45.0) * 2.0
        return max(10.0, 70.0 - (value - 60.0) * 3.0)

    if kind == "vibration":
        if value <= 3:
            return 100.0
        if value <= 5:
            return 100.0 - (value - 3.0) * 12.5
        return max(10.0, 75.0 - (value - 5.0) * 13.0)

    if kind in {"current", "load"}:
        recent = (
            db.query(models.SensorReading)
            .filter_by(machine_id=machine.id, reading_type=reading_type)
            .order_by(models.SensorReading.recorded_at.desc())
            .limit(10)
            .all()
        )
        prior = [r.value for r in recent if r.value != value]
        if len(prior) >= 3:
            baseline = sum(prior) / len(prior)
            if baseline > 0:
                ratio = value / baseline
                if ratio <= 1.20:
                    return 100.0
                if ratio <= 1.50:
                    return max(60.0, 100.0 - (ratio - 1.20) * 133.0)
                return max(10.0, 60.0 - (ratio - 1.50) * 60.0)
        return 100.0

    # Humidity and other informational sensors do not directly penalize
    # machine health without a machine-specific engineering threshold.
    return 100.0


def _apply_live_sensor_health(db: Session, machine: models.Machine, reading: models.SensorReading):
    """Gradually move the stored health score according to live sensor stress."""
    condition = _reading_condition_score(db, machine, reading.reading_type, reading.value)

    if condition < 40:
        delta = -5
    elif condition < 70:
        delta = -2
    elif condition < 90:
        delta = -1
    else:
        # Normal readings do not instantly restore health. A small recovery
        # models stabilization after the machine returns to normal operation.
        delta = 1

    old_score = int(machine.health_score or 0)
    new_score = max(0, min(100, old_score + delta))

    if new_score != old_score:
        machine.health_score = new_score
        machine.status = (
            models.HealthStatus.healthy if new_score >= 70
            else models.HealthStatus.attention if new_score >= 40
            else models.HealthStatus.critical
        )
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

    # Live data now has two effects:
    # 1) the existing alert engine evaluates machine conditions;
    # 2) this transparent sensor-health layer adjusts the stored health score.
    _apply_live_sensor_health(db, machine, reading)
    evaluate_machine(db, machine)
    _check_sensor_anomaly(db, machine, reading)

    return {"accepted": True, "machine": machine.name, "recorded_at": reading.recorded_at}
