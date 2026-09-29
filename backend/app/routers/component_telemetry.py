from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..sensor_models import ComponentSensor, ComponentSensorReading
from .devices import IngestPayload, _device_command_clients, _process_reading, _publish_reading

router = APIRouter(prefix='/api/devices', tags=['component-telemetry'])


class ComponentTelemetryIn(BaseModel):
    sensor_id: int
    value: float
    unit: str | None = None
    recorded_at: datetime | None = None
    event_id: str | None = None


def _machine_for_key(db, key):
    machine = db.query(models.Machine).filter_by(device_key=key, iot_enabled=True, archived=False).first()
    if not machine:
        raise HTTPException(401, 'invalid or disabled device key')
    return machine


def _normalized_time(value: datetime | None) -> datetime:
    if value is None:
        return datetime.utcnow()
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


@router.post('/component-telemetry')
async def ingest_component_telemetry(
    payload: ComponentTelemetryIn,
    x_device_key: str | None = Header(default=None, alias='X-Device-Key'),
    db: Session = Depends(get_db),
):
    if not x_device_key:
        raise HTTPException(401, 'X-Device-Key is required')

    machine = _machine_for_key(db, x_device_key)
    sensor = (
        db.query(ComponentSensor)
        .join(models.Component, models.Component.id == ComponentSensor.component_id)
        .filter(
            ComponentSensor.id == payload.sensor_id,
            models.Component.machine_id == machine.id,
            ComponentSensor.enabled.is_(True),
        )
        .first()
    )
    if not sensor:
        raise HTTPException(404, 'sensor not found for this device')

    if sensor.min_value is not None and payload.value < sensor.min_value:
        raise HTTPException(400, 'value below configured sensor minimum')
    if sensor.max_value is not None and payload.value > sensor.max_value:
        raise HTTPException(400, 'value above configured sensor maximum')

    # event_id is scoped to the component sensor. Retries must be idempotent,
    # just like the established /api/devices/ingest contract.
    component_event_id = None
    if payload.event_id:
        component_event_id = f'{machine.id}:{sensor.id}:{payload.event_id}'
        existing = (
            db.query(ComponentSensorReading)
            .filter_by(sensor_id=sensor.id, external_id=component_event_id)
            .first()
        )
        if existing:
            return {
                'accepted': True,
                'status': 'duplicate',
                'machine_id': machine.id,
                'component_id': sensor.component_id,
                'sensor_id': sensor.id,
                'reading_id': existing.id,
                'event_id': payload.event_id,
            }

    recorded_at = _normalized_time(payload.recorded_at)
    component_reading = ComponentSensorReading(
        sensor_id=sensor.id,
        component_id=sensor.component_id,
        reading_type=sensor.reading_type,
        value=payload.value,
        unit=payload.unit or sensor.unit,
        source='device',
        external_id=component_event_id,
        recorded_at=recorded_at,
    )
    db.add(component_reading)
    db.commit()
    db.refresh(component_reading)

    # Feed the same established telemetry pipeline used by legacy devices.
    # This preserves safety-policy evaluation, alerts, anomaly/degradation
    # processing, realtime publication, and the existing auto-shutdown command
    # path. Namespace the event id so the component and machine records cannot
    # collide while retries remain idempotent.
    machine_payload = IngestPayload(
        reading_type=sensor.reading_type,
        value=payload.value,
        unit=payload.unit or sensor.unit,
        recorded_at=recorded_at,
        event_id=f'component:{component_event_id}' if component_event_id else None,
    )
    machine_reading, behaviour, safety, degradation = _process_reading(db, machine, machine_payload)
    await _publish_reading(machine, machine_reading, behaviour, safety, degradation)

    if safety and safety.get('shutdown_requested'):
        client = _device_command_clients.get(machine.id)
        if client:
            try:
                await client.send_json({
                    'type': 'shutdown',
                    'machine_id': machine.id,
                    'reason': safety['message'],
                    'reading_type': machine_reading.reading_type,
                    'value': machine_reading.value,
                    'threshold': safety.get('threshold'),
                    'event_id': safety.get('event_id'),
                })
                safety['device_command_sent'] = True
            except Exception:
                _device_command_clients.pop(machine.id, None)

    return {
        'accepted': True,
        'status': 'created',
        'machine_id': machine.id,
        'component_id': sensor.component_id,
        'sensor_id': sensor.id,
        'reading_id': component_reading.id,
        'machine_reading_id': machine_reading.id,
        'event_id': payload.event_id,
        'reading_type': component_reading.reading_type,
        'value': component_reading.value,
        'unit': component_reading.unit,
        'recorded_at': component_reading.recorded_at,
        'behaviour': behaviour,
        'safety': safety,
        'degradation': degradation,
    }
