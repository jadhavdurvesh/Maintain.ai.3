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
from ..deps import get_current_user, CurrentUser
from ..alerts_engine import evaluate_machine
from ..ml.online import update_online_state
from ..ml.intelligence import process_telemetry
from ..ml.temporal_features import materialize_windows
from ..ml.anomaly_events import create_anomaly_event
from ..notification_service import notify_machine_workers
from ..supabase_realtime import broadcast as supabase_broadcast

router = APIRouter(prefix="/api/devices", tags=["devices"])

def _get_scoped_machine(db: Session, machine_id: int, current: CurrentUser, admin_only: bool = False):
    if admin_only and current.role != models.UserRole.admin.value:
        raise HTTPException(403, "administrator access required")
    machine = db.query(models.Machine).filter(models.Machine.id == machine_id, models.Machine.organization_id == current.organization_id, models.Machine.archived.is_(False)).first()
    if not machine:
        raise HTTPException(404, "machine not found")
    if current.role == models.UserRole.technician.value and not db.query(models.UserMachineAssignment).filter_by(user_id=current.id, machine_id=machine_id).first():
        raise HTTPException(404, "machine not assigned to this worker")
    return machine


class TelemetryStream:
    """Process-local fan-out partitioned by organization."""
    def __init__(self):
        self._clients = {}

    async def connect(self, websocket, organization_id: int, machine_ids: set[int] | None = None):
        await websocket.accept()
        self._clients.setdefault(organization_id, {})[websocket] = machine_ids

    def disconnect(self, websocket, organization_id: int | None = None):
        if organization_id is not None:
            clients = self._clients.get(organization_id, {})
            clients.pop(websocket, None)
            if not clients:
                self._clients.pop(organization_id, None)
            return
        for org_id, clients in list(self._clients.items()):
            clients.pop(websocket, None)
            if not clients:
                self._clients.pop(org_id, None)

    async def broadcast(self, organization_id: int, event):
        stale = []
        machine_id = event.get("machine_id")
        for client, allowed_machine_ids in tuple(self._clients.get(organization_id, {}).items()):
            if allowed_machine_ids is not None and machine_id not in allowed_machine_ids:
                continue
            try:
                await client.send_json(event)
            except Exception:
                stale.append(client)
        for client in stale:
            self.disconnect(client, organization_id)


telemetry_stream = TelemetryStream()
_device_command_clients = {}


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
        if machine.status == models.HealthStatus.critical:
            _ensure_triggered_maintenance(
                db,
                machine,
                trigger="corrective",
                reason=f"{machine.name}: machine health reached a critical state.",
                scheduled_date=datetime.utcnow(),
            )


class DeviceStatusOut(BaseModel):
    iot_enabled: bool
    has_key: bool
    device_key: str | None = None


class SafetyPolicyPayload(BaseModel):
    enabled: bool = False
    monitored_reading_type: str = "temperature"
    unit: str | None = None
    warning_low: float | None = None
    warning_high: float | None = None
    shutdown_low: float | None = None
    shutdown_high: float | None = None
    auto_shutdown_enabled: bool = False


class IngestPayload(BaseModel):
    reading_type: str
    value: float
    unit: str | None = None
    recorded_at: datetime | None = None
    event_id: str | None = None


def _ensure_triggered_maintenance(db: Session, machine: models.Machine, *, trigger: str, reason: str, scheduled_date: datetime | None = None):
    """Create one open maintenance action for a safety/health trigger, idempotently."""
    if trigger == "breakdown":
        description_prefix = "AUTO-BREAKDOWN:"
        maintenance_type = "breakdown"
        due = scheduled_date or datetime.utcnow()
    else:
        description_prefix = "AUTO-CORRECTIVE:"
        maintenance_type = "corrective"
        due = scheduled_date or datetime.utcnow()

    existing = (
        db.query(models.MaintenanceRecord)
        .filter(
            models.MaintenanceRecord.machine_id == machine.id,
            models.MaintenanceRecord.status != models.MaintenanceStatus.completed,
            models.MaintenanceRecord.description.like(description_prefix + "%"),
        )
        .order_by(models.MaintenanceRecord.id.desc())
        .first()
    )
    if existing:
        return existing

    record = models.MaintenanceRecord(
        machine_id=machine.id,
        type=maintenance_type,
        description=f"{description_prefix} {reason}",
        scheduled_date=due,
        status=models.MaintenanceStatus.scheduled,
    )
    db.add(record)
    machine.next_maintenance_date = due
    db.commit()
    db.refresh(record)
    return record


def _evaluate_safety_policy(db: Session, machine: models.Machine, reading: models.SensorReading):
    policy = db.query(models.MachineSafetyPolicy).filter_by(
        machine_id=machine.id,
        monitored_reading_type=reading.reading_type,
    ).first()
    if not policy or not policy.enabled:
        return None

    value = float(reading.value)
    low_warning = policy.warning_low is not None and value <= policy.warning_low
    high_warning = policy.warning_high is not None and value >= policy.warning_high
    low_shutdown = policy.shutdown_low is not None and value <= policy.shutdown_low
    high_shutdown = policy.shutdown_high is not None and value >= policy.shutdown_high

    event_type = "shutdown_threshold" if (low_shutdown or high_shutdown) else "warning_threshold" if (low_warning or high_warning) else None
    if not event_type:
        return None

    threshold = (policy.shutdown_low if low_shutdown else policy.shutdown_high) if event_type == "shutdown_threshold" else (policy.warning_low if low_warning else policy.warning_high)
    recent = (
        db.query(models.MachineSafetyEvent)
        .filter_by(machine_id=machine.id, event_type=event_type, reading_type=reading.reading_type)
        .order_by(models.MachineSafetyEvent.created_at.desc())
        .first()
    )
    if recent and (datetime.utcnow() - recent.created_at).total_seconds() < 300:
        # Do not suppress an unacknowledged automatic shutdown just because the
        # threshold event was already recorded. A device may have connected
        # after the first crossing (common with serverless reconnects).
        if event_type == "shutdown_threshold" and policy.auto_shutdown_enabled and not recent.device_acknowledged:
            return {
                "event_id": recent.id,
                "type": recent.event_type,
                "shutdown_requested": True,
                "device_command_available": machine.id in _device_command_clients,
                "threshold": recent.threshold,
                "message": recent.message,
                "pending_ack": True,
            }
        return None

    shutdown_requested = event_type == "shutdown_threshold" and policy.auto_shutdown_enabled
    direction = "below" if (low_shutdown or low_warning) else "above"
    message = f"{machine.name}: {reading.reading_type} is {direction} the configured {'shutdown' if shutdown_requested else 'warning'} threshold ({value:g}{reading.unit or policy.unit or ''}; limit {threshold:g}{reading.unit or policy.unit or ''})."
    event = models.MachineSafetyEvent(
        machine_id=machine.id, event_type=event_type, reading_type=reading.reading_type,
        value=value, threshold=threshold, message=message, shutdown_requested=shutdown_requested,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    if event_type == "warning_threshold":
        db.add(models.Alert(
            machine_id=machine.id, alert_type=f"safety_warning_{reading.reading_type}",
            severity=models.AlertSeverity.warning, message=message,
        ))
        db.commit()
        notify_machine_workers(
            db, machine.id, "safety_warning", "Machine Safety Warning", message,
            {"route": "machine_alert", "machine_id": machine.id, "event_id": event.id},
        )

    if event_type == "shutdown_threshold":
        _ensure_triggered_maintenance(
            db,
            machine,
            trigger="breakdown",
            reason=message,
            scheduled_date=datetime.utcnow(),
        )
        notify_machine_workers(
            db, machine.id, "safety_shutdown", "Machine Safety Limit Crossed", message,
            {"route": "machine_alert", "machine_id": machine.id, "event_id": event.id, "auto_shutdown": shutdown_requested},
        )

    device_command_available = machine.id in _device_command_clients


    return {
        "event_id": event.id, "type": event_type, "shutdown_requested": shutdown_requested,
        "device_command_available": device_command_available, "threshold": threshold, "message": message,
    }


def _process_reading(db: Session, machine: models.Machine, payload: IngestPayload):
    """Single source of truth for REST and WebSocket sensor ingestion."""
    reading = models.SensorReading(
        machine_id=machine.id,
        reading_type=payload.reading_type,
        value=payload.value,
        unit=payload.unit,
        source="sensor",
        external_id=payload.event_id,
        recorded_at=(payload.recorded_at.astimezone(timezone.utc).replace(tzinfo=None) if payload.recorded_at and payload.recorded_at.tzinfo else (payload.recorded_at if payload.recorded_at else datetime.utcnow())),
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    _apply_live_sensor_health(db, machine, reading)
    evaluate_machine(db, machine)
    _check_sensor_anomaly(db, machine, reading)
    behaviour = update_online_state(db, machine, reading)
    degradation = process_telemetry(db, machine.id, reading.recorded_at)
    try:
        materialize_windows(db, machine.id, reading.recorded_at)
    except Exception:
        # Feature materialization must never take down telemetry ingestion.
        db.rollback()

    # Confirmed Lab anomalies are durable and deduplicated. A worker push is
    # emitted only the first time an event reaches high/critical severity.
    safety = _evaluate_safety_policy(db, machine, reading)
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

    return reading, behaviour, safety, degradation


async def _publish_reading(machine, reading, behaviour, safety=None, degradation=None):
    event = {
        "type": "telemetry", "machine_id": machine.id, "machine": machine.name,
        "reading_id": reading.id, "reading_type": reading.reading_type,
        "value": reading.value, "unit": reading.unit,
        "recorded_at": reading.recorded_at.isoformat() if reading.recorded_at else None,
        "behaviour": behaviour,
        "safety": safety,
        "degradation": degradation,
    }
    await telemetry_stream.broadcast(machine.organization_id, {**event, "organization_id": machine.organization_id})
    await supabase_broadcast("org:" + str(machine.organization_id) + ":telemetry", "telemetry", event)
    await supabase_broadcast("machine:" + str(machine.id) + ":telemetry", "telemetry", event)


@router.websocket("/stream")
async def telemetry_stream_websocket(websocket: WebSocket):
    """Authorized live telemetry stream for web/mobile clients."""
    from ..supabase_auth import verify_access_token
    from ..auth import decode_access_token
    from ..bootstrap import BOOTSTRAP_ORG_ID

    token = websocket.query_params.get("token")
    application = (websocket.query_params.get("application") or "engineering").strip().lower()
    if application not in {"engineering", "android", "workforce"}:
        await websocket.close(code=1008, reason="invalid application context")
        return

    db = SessionLocal()
    organization_id = None
    user_id = None
    allowed_machine_ids = None
    try:
        if token:
            claims = verify_access_token(token)
            if not claims:
                claims = decode_access_token(token)
            if not claims:
                await websocket.close(code=1008, reason="invalid or expired token")
                return

            sid = claims.get("sub")
            try:
                supabase_id = str(sid)
                user = db.query(models.User).filter_by(supabase_user_id=supabase_id).first()
                if not user and claims.get("email"):
                    user = db.query(models.User).filter_by(email=claims.get("email")).first()
                if user:
                    access = db.query(models.UserApplicationAccess).filter(
                        models.UserApplicationAccess.user_id == user.id,
                        models.UserApplicationAccess.application == application,
                        models.UserApplicationAccess.enabled.is_(True),
                    ).first()
                    if not access:
                        await websocket.close(code=1008, reason="application access denied")
                        return
                    organization_id = user.organization_id
                    user_id = user.id
                    if user.role == models.UserRole.technician:
                        allowed_machine_ids = {row[0] for row in db.query(models.UserMachineAssignment.machine_id)
                            .join(models.Machine, models.Machine.id == models.UserMachineAssignment.machine_id)
                            .filter(models.UserMachineAssignment.user_id == user.id,
                                    models.Machine.organization_id == organization_id,
                                    models.Machine.archived.is_(False)).all()}
                else:
                    payload = decode_access_token(token)
                    user_id = int(payload["sub"])
                    organization_id = int(payload["org"])
                    user = db.get(models.User, user_id)
                    if not user or not user.active or user.organization_id != organization_id:
                        raise ValueError("unauthorized")
                    access = db.query(models.UserApplicationAccess).filter(
                        models.UserApplicationAccess.user_id == user.id,
                        models.UserApplicationAccess.application == application,
                        models.UserApplicationAccess.enabled.is_(True),
                    ).first()
                    if not access:
                        raise ValueError("application access denied")
                    if user.role == models.UserRole.technician:
                        allowed_machine_ids = {row[0] for row in db.query(models.UserMachineAssignment.machine_id)
                            .join(models.Machine, models.Machine.id == models.UserMachineAssignment.machine_id)
                            .filter(models.UserMachineAssignment.user_id == user.id,
                                    models.Machine.organization_id == organization_id,
                                    models.Machine.archived.is_(False)).all()}
            except Exception:
                await websocket.close(code=1008, reason="unauthorized")
                return
        else:
            from ..deps import auth_required
            if auth_required():
                await websocket.close(code=1008, reason="authentication required")
                return
            organization_id = BOOTSTRAP_ORG_ID

        await websocket.accept()
        await websocket.send_json({
            "type": "stream_connected",
            "protocol": "maintain-ai",
            "version": 2,
            "organization_id": organization_id,
            "application": application,
        })

        # This stream is organization-filtered at publication time and
        # additionally rejects arbitrary client-side machine subscriptions.
        await telemetry_stream.connect(websocket, organization_id, allowed_machine_ids)
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                await websocket.send_json({"type": "error", "message": "unsupported message type"})
    except WebSocketDisconnect:
        pass
    finally:
        telemetry_stream.disconnect(websocket, organization_id if organization_id is not None else None)
        db.close()

@router.get("/{machine_id}/status", response_model=DeviceStatusOut)
def device_status(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    machine = _get_scoped_machine(db, machine_id, current)
    return DeviceStatusOut(iot_enabled=machine.iot_enabled, has_key=bool(machine.device_key))


@router.post("/{machine_id}/enable", response_model=DeviceStatusOut)
def enable_device(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    machine = _get_scoped_machine(db, machine_id, current, admin_only=True)
    machine.iot_enabled = True
    machine.device_key = secrets.token_hex(16)
    db.commit()
    audit.log_event(db, "machine", machine.id, "iot_enabled", f"Live sensor integration enabled for {machine.name}")
    return DeviceStatusOut(iot_enabled=True, has_key=True, device_key=machine.device_key)


@router.post("/{machine_id}/disable", response_model=DeviceStatusOut)
def disable_device(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    machine = _get_scoped_machine(db, machine_id, current, admin_only=True)
    machine.iot_enabled = False
    db.commit()
    audit.log_event(db, "machine", machine.id, "iot_disabled", f"Live sensor integration disabled for {machine.name}")
    return DeviceStatusOut(iot_enabled=False, has_key=bool(machine.device_key))


@router.post("/ping")
def device_ping(
    x_device_key: str = Header(..., alias="X-Device-Key"),
    db: Session = Depends(get_db),
):
    """Validate a machine device key without creating telemetry or ML state."""
    machine = db.query(models.Machine).filter_by(device_key=x_device_key).first()
    if not machine or not machine.iot_enabled:
        raise HTTPException(401, "invalid or disabled device key")
    return {
        "ok": True,
        "machine_id": machine.id,
        "machine": machine.name,
        "iot_enabled": True,
    }


@router.post("/ingest")
async def ingest_reading(
    payload: IngestPayload,
    x_device_key: str = Header(..., alias="X-Device-Key"),
    db: Session = Depends(get_db),
):
    machine = db.query(models.Machine).filter_by(device_key=x_device_key).first()
    if not machine or not machine.iot_enabled:
        raise HTTPException(401, "invalid or disabled device key")
    if payload.event_id:
        existing = db.query(models.SensorReading).filter_by(external_id=payload.event_id).first()
        if existing:
            return {"status": "duplicate", "reading_id": existing.id}
    reading, behaviour, safety, degradation = _process_reading(db, machine, payload)
    await _publish_reading(machine, reading, behaviour, safety, degradation)
    if safety and safety.get("shutdown_requested"):
        client = _device_command_clients.get(machine.id)
        if client:
            try:
                await client.send_json({
                    "type": "shutdown",
                    "machine_id": machine.id,
                    "reason": safety["message"],
                    "reading_type": reading.reading_type,
                    "value": reading.value,
                    "threshold": safety.get("threshold"),
                    "event_id": safety.get("event_id"),
                })
                safety["device_command_sent"] = True
            except Exception:
                _device_command_clients.pop(machine.id, None)
    return {
        "accepted": True,
        "machine": machine.name,
        "recorded_at": reading.recorded_at,
        "behaviour": behaviour,
        "safety": safety,
        "degradation": degradation,
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

        _device_command_clients[machine.id] = websocket

        await websocket.send_json({
            "type": "authenticated",
            "machine_id": machine.id,
            "machine": machine.name,
            "protocol": "maintain-ai",
            "version": 1,
        })

        pending_shutdown = (
            db.query(models.MachineSafetyEvent)
            .filter(
                models.MachineSafetyEvent.machine_id == machine.id,
                models.MachineSafetyEvent.event_type == "shutdown_threshold",
                models.MachineSafetyEvent.shutdown_requested.is_(True),
                models.MachineSafetyEvent.device_acknowledged.is_(False),
            )
            .order_by(models.MachineSafetyEvent.created_at.desc())
            .first()
        )
        if pending_shutdown:
            await websocket.send_json({
                "type": "shutdown",
                "machine_id": machine.id,
                "reason": pending_shutdown.message,
                "reading_type": pending_shutdown.reading_type,
                "value": pending_shutdown.value,
                "threshold": pending_shutdown.threshold,
                "event_id": pending_shutdown.id,
                "pending": True,
            })

        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            if message.get("type") in {"shutdown_ack", "shutdown_test_ack"}:
                event_id = message.get("event_id")
                event = db.get(models.MachineSafetyEvent, int(event_id)) if event_id else (
                    db.query(models.MachineSafetyEvent)
                    .filter_by(machine_id=machine.id, event_type="shutdown_threshold")
                    .order_by(models.MachineSafetyEvent.created_at.desc())
                    .first()
                )
                if event:
                    event.device_acknowledged = True
                    db.commit()
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

            reading, behaviour, safety, degradation = _process_reading(db, machine, payload)
            await _publish_reading(machine, reading, behaviour, safety, degradation)
            if safety and safety.get("shutdown_requested"):
                await websocket.send_json({
                    "type": "shutdown",
                    "machine_id": machine.id,
                    "reason": safety["message"],
                    "reading_type": reading.reading_type,
                    "value": reading.value,
                    "threshold": safety.get("threshold"),
                    "event_id": safety.get("event_id"),
                })
            await websocket.send_json({
                "type": "reading_accepted",
                "reading_id": reading.id,
                "reading_type": reading.reading_type,
                "value": reading.value,
                "unit": reading.unit,
                "recorded_at": reading.recorded_at.isoformat() if reading.recorded_at else None,
                "behaviour": behaviour,
                "safety": safety,
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


@router.get("/{machine_id}/safety")
def get_safety_policy(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    machine = _get_scoped_machine(db, machine_id, current)
    policies = db.query(models.MachineSafetyPolicy).filter_by(machine_id=machine.id).order_by(models.MachineSafetyPolicy.id.asc()).all()
    rows = [{c.name: getattr(policy, c.name) for c in models.MachineSafetyPolicy.__table__.columns if c.name not in {"id", "machine_id"}} for policy in policies]
    return {"configured": bool(rows), "enabled": any(bool(row.get("enabled")) for row in rows), "policies": rows, "auto_shutdown_enabled": any(bool(row.get("auto_shutdown_enabled")) for row in rows)}

@router.put("/{machine_id}/safety")
def set_safety_policy(machine_id: int, payload: SafetyPolicyPayload, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    machine = _get_scoped_machine(db, machine_id, current, admin_only=True)
    if payload.auto_shutdown_enabled and not payload.enabled:
        raise HTTPException(400, "Enable threshold monitoring before enabling automatic shutdown.")
    if payload.shutdown_low is not None and payload.warning_low is not None and payload.warning_low < payload.shutdown_low:
        raise HTTPException(400, "Low warning threshold must be reached before the low shutdown threshold.")
    if payload.shutdown_high is not None and payload.warning_high is not None and payload.warning_high > payload.shutdown_high:
        raise HTTPException(400, "High warning threshold must be reached before the high shutdown threshold.")
    if payload.shutdown_low is not None and payload.shutdown_high is not None and payload.shutdown_low >= payload.shutdown_high:
        raise HTTPException(400, "Low shutdown threshold must be below high shutdown threshold.")
    policy = db.query(models.MachineSafetyPolicy).filter_by(machine_id=machine_id, monitored_reading_type=payload.monitored_reading_type).first()
    if not policy:
        policy = models.MachineSafetyPolicy(machine_id=machine_id)
        db.add(policy)
    for key, value in payload.model_dump().items():
        setattr(policy, key, value)
    policy.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(policy)
    audit.log_event(db, "machine", machine.id, "safety_policy_updated", f"Safety thresholds updated for {machine.name} ({policy.monitored_reading_type})")
    return {"configured": True, "policies": [{c.name: getattr(p, c.name) for c in models.MachineSafetyPolicy.__table__.columns if c.name not in {"id", "machine_id"}} for p in db.query(models.MachineSafetyPolicy).filter_by(machine_id=machine.id).all()], **{c.name: getattr(policy, c.name) for c in models.MachineSafetyPolicy.__table__.columns if c.name not in {"id", "machine_id"}}}

@router.post("/{machine_id}/safety/test-shutdown")
async def test_shutdown(machine_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    machine = _get_scoped_machine(db, machine_id, current, admin_only=True)
    client = _device_command_clients.get(machine_id)
    if not client:
        raise HTTPException(409, "Safety device WebSocket is not connected.")
    await client.send_json({"type": "shutdown_test", "machine_id": machine_id, "reason": "Manual safety shutdown test"})
    return {"sent": True, "machine_id": machine_id}
