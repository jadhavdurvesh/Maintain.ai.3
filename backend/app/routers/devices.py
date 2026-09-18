"""
Optional live-sensor integration for the Lab branch.

REST ingestion remains backwards compatible. The Lab branch additionally
supports a long-lived WebSocket connection for continuous telemetry.
"""
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Header, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from .. import models, audit
from ..database import get_db, SessionLocal
from ..alerts_engine import evaluate_machine
from ..ml.online import update_online_state
from ..ml.temporal_features import materialize_windows
from ..ml.anomaly_events import create_anomaly_event
from ..notification_service import notify_machine_workers

router = APIRouter(prefix="/api/devices", tags=["devices"])


class TelemetryStream:
    """Process-local fan-out from device ingestion to live dashboard clients."""
    def __init__(self):
        self._clients = set()

    async def connect(self, websocket):
        await websocket.accept()
        self._clients.add(websocket)

    def disconnect(self, websocket):
        self._clients.discard(websocket)

    async def broadcast(self, event):
        stale = []
        for client in tuple(self._clients):
            try:
                await client.send_json(event)
            except Exception:
                stale.append(client)
        for client in stale:
            self.disconnect(client)


telemetry_stream = TelemetryStream()


def _check_sensor_anomaly(db: Session, machine: models.Machine, reading: models.SensorReading):
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


def _apply_live_sensor_health(db: Session, machine: models.Machine, reading: models.SensorReading):
    condition = _reading_condition_score(db, machine, reading.reading_type, reading.value)
    delta = -5 if condition < 40 else -2 if condition < 70 else -1 if condition < 90 else 1
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
    device_key: str | None = None


class IngestPayload(BaseModel):
    reading_type: str
    value: float
    unit: str | None = None
    recorded_at: datetime | None = None


def _process_reading(db: Session, machine: models.Machine, payload: IngestPayload):
    """Single source of truth for REST and WebSocket sensor ingestion."""
    reading = models.SensorReading(
        machine_id=machine.id,
        reading_type=payload.reading_type,
        value=payload.value,
        unit=payload.unit,
        source="sensor",
        recorded_at=(payload.recorded_at.astimezone(timezone.utc).replace(tzinfo=None) if payload.recorded_at and payload.recorded_at.tzinfo else (payload.recorded_at if payload.recorded_at else datetime.utcnow())),
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    _apply_live_sensor_health(db, machine, reading)
    evaluate_machine(db, machine)
    _check_sensor_anomaly(db, machine, reading)
    behaviour = update_online_state(db, machine, reading)
    try:
        materialize_windows(db, machine.id, reading.recorded_at)
    except Exception:
        # Feature materialization must never take down telemetry ingestion.
        db.rollback()

    # Confirmed Lab anomalies are durable and deduplicated. A worker push is
    # emitted only the first time an event reaches high/critical severity.
    anomaly_event = None
    if behaviour.get("persistent_change"):
        anomaly_message = (
            f"{machine.name}: {reading.reading_type} behaviour changed from its learned baseline. "
            f"Anomaly score {behaviour.get('anomaly_score', 0):.2f}."
        )
        anomaly_event = create_anomaly_event(db, machine, behaviour, anomaly_message)
        if (
            anomaly_event
            and not anomaly_event.notified
            and anomaly_event.severity in {models.AlertSeverity.high, models.AlertSeverity.critical}
        ):
            notify_machine_workers(
                db,
                machine.id,
                "ml_anomaly",
                "Machine Behaviour Anomaly",
                anomaly_message,
                {
                    "route": "machine_alert",
                    "machine_id": machine.id,
                    "anomaly_event_id": anomaly_event.id,
                    "reading_type": reading.reading_type,
                    "severity": anomaly_event.severity.value,
                },
            )
            anomaly_event.notified = True
            db.commit()

    return reading, behaviour


async def _publish_reading(machine, reading, behaviour):
    await telemetry_stream.broadcast({
        "type": "telemetry", "machine_id": machine.id, "machine": machine.name,
        "reading_id": reading.id, "reading_type": reading.reading_type,
        "value": reading.value, "unit": reading.unit,
        "recorded_at": reading.recorded_at.isoformat() if reading.recorded_at else None,
        "behaviour": behaviour,
    })


@router.websocket("/stream")
async def telemetry_stream_websocket(websocket: WebSocket):
    """Live dashboard stream; JWT is supplied as ?token= for browser WebSockets."""
    from ..auth import decode_access_token
    from ..bootstrap import BOOTSTRAP_ORG_ID
    from ..deps import auth_required
    token = websocket.query_params.get("token")
    db = SessionLocal()
    try:
        if token:
            payload = decode_access_token(token)
            if not payload:
                await websocket.close(code=1008, reason="invalid or expired token"); return
            try:
                user_id, organization_id = int(payload["sub"]), int(payload["org"])
            except (KeyError, TypeError, ValueError):
                await websocket.close(code=1008, reason="invalid authentication token"); return
            user = db.get(models.User, user_id)
            if not user or not user.active or user.organization_id != organization_id:
                await websocket.close(code=1008, reason="unauthorized"); return
        elif auth_required():
            await websocket.close(code=1008, reason="authentication required"); return
        else:
            organization_id = BOOTSTRAP_ORG_ID
        await telemetry_stream.connect(websocket)
        await websocket.send_json({"type":"stream_connected","protocol":"maintain-ai","version":1,"organization_id":organization_id})
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await websocket.send_json({"type":"pong"})
            else:
                await websocket.send_json({"type":"error","message":"unsupported message type"})
    except WebSocketDisconnect:
        pass
    finally:
        telemetry_stream.disconnect(websocket)
        db.close()


@router.get("/{machine_id}/status", response_model=DeviceStatusOut)
def device_status(machine_id: int, db: Session = Depends(get_db)):
    machine = db.get(models.Machine, machine_id)
    if not machine:
        raise HTTPException(404, "machine not found")
    return DeviceStatusOut(iot_enabled=machine.iot_enabled, has_key=bool(machine.device_key))


@router.post("/{machine_id}/enable", response_model=DeviceStatusOut)
def enable_device(machine_id: int, db: Session = Depends(get_db)):
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
    machine = db.query(models.Machine).filter_by(device_key=x_device_key).first()
    if not machine or not machine.iot_enabled:
        raise HTTPException(401, "invalid or disabled device key")
    reading, behaviour = _process_reading(db, machine, payload)
    return {
        "accepted": True,
        "machine": machine.name,
        "recorded_at": reading.recorded_at,
        "behaviour": behaviour,
    }


@router.websocket("/ws")
async def device_websocket(websocket: WebSocket):
    """Long-lived Lab telemetry channel.

    Handshake:
      {"type":"authenticate","device_key":"..."}
    Then repeatedly send:
      {"type":"reading","reading_type":"temperature","value":29.3,"unit":"°C"}

    The existing REST endpoint remains available for older devices.
    """
    await websocket.accept()
    db = SessionLocal()
    try:
        try:
            auth_message = await websocket.receive_json()
        except Exception:
            await websocket.close(code=1008, reason="authentication required")
            return

        if auth_message.get("type") != "authenticate" or not auth_message.get("device_key"):
            await websocket.send_json({"type": "error", "message": "authentication required"})
            await websocket.close(code=1008)
            return

        machine = (
            db.query(models.Machine)
            .filter_by(device_key=str(auth_message["device_key"]), iot_enabled=True)
            .first()
        )
        if not machine:
            await websocket.send_json({"type": "error", "message": "invalid or disabled device key"})
            await websocket.close(code=1008)
            return

        await websocket.send_json({
            "type": "authenticated",
            "machine_id": machine.id,
            "machine": machine.name,
            "protocol": "maintain-ai",
            "version": 1,
        })

        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            if message.get("type") != "reading":
                await websocket.send_json({"type": "error", "message": "unsupported message type"})
                continue
            try:
                payload = IngestPayload.model_validate(message)
            except ValidationError as exc:
                await websocket.send_json({"type": "error", "message": "invalid reading payload", "errors": exc.errors()})
                continue

            # Re-open the machine from the DB for each message so key rotation
            # or IoT disablement takes effect on an existing socket too.
            machine = (
                db.query(models.Machine)
                .filter_by(id=machine.id, device_key=str(auth_message["device_key"]), iot_enabled=True)
                .first()
            )
            if not machine:
                await websocket.send_json({"type": "error", "message": "device disabled or key rotated"})
                await websocket.close(code=1008)
                return

            reading, behaviour = _process_reading(db, machine, payload)
            await _publish_reading(machine, reading, behaviour)
            await websocket.send_json({
                "type": "reading_accepted",
                "reading_id": reading.id,
                "reading_type": reading.reading_type,
                "value": reading.value,
                "unit": reading.unit,
                "recorded_at": reading.recorded_at.isoformat() if reading.recorded_at else None,
                "behaviour": behaviour,
            })
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f"[iot-ws] connection error: {type(exc).__name__}: {exc}")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        db.close()
