from datetime import datetime
from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .. import models
from ..database import get_db
from ..sensor_models import ComponentSensor, ComponentSensorReading

router = APIRouter(prefix='/api/devices', tags=['component-telemetry'])
class ComponentTelemetryIn(BaseModel):
    sensor_id: int
    value: float
    unit: str | None = None
    recorded_at: datetime | None = None
    event_id: str | None = None

def _machine_for_key(db, key):
    m=db.query(models.Machine).filter_by(device_key=key,iot_enabled=True,archived=False).first()
    if not m: raise HTTPException(401,'invalid or disabled device key')
    return m

@router.post('/component-telemetry')
def ingest_component_telemetry(payload:ComponentTelemetryIn,x_device_key:str|None=Header(default=None,alias='X-Device-Key'),db:Session=Depends(get_db)):
    if not x_device_key: raise HTTPException(401,'X-Device-Key is required')
    machine=_machine_for_key(db,x_device_key)
    sensor=db.query(ComponentSensor).join(models.Component,models.Component.id==ComponentSensor.component_id).filter(ComponentSensor.id==payload.sensor_id,models.Component.machine_id==machine.id,ComponentSensor.enabled.is_(True)).first()
    if not sensor: raise HTTPException(404,'sensor not found for this device')
    if sensor.min_value is not None and payload.value < sensor.min_value: raise HTTPException(400,'value below configured sensor minimum')
    if sensor.max_value is not None and payload.value > sensor.max_value: raise HTTPException(400,'value above configured sensor maximum')
    reading=ComponentSensorReading(sensor_id=sensor.id,component_id=sensor.component_id,reading_type=sensor.reading_type,value=payload.value,unit=payload.unit or sensor.unit,source='device',recorded_at=payload.recorded_at or datetime.utcnow())
    db.add(reading);db.commit();db.refresh(reading)
    return {'accepted':True,'machine_id':machine.id,'component_id':sensor.component_id,'sensor_id':sensor.id,'reading_id':reading.id,'reading_type':reading.reading_type,'value':reading.value,'unit':reading.unit,'recorded_at':reading.recorded_at}
