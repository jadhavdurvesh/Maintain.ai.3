from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .. import models
from ..database import get_db
from ..deps import get_current_user, CurrentUser
from ..sensor_models import ComponentSensor, ComponentSensorReading

router = APIRouter(prefix='/api', tags=['component-sensors'])

class SensorIn(BaseModel):
    name: str
    reading_type: str
    unit: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    enabled: bool = True

class ReadingIn(BaseModel):
    sensor_id: int
    value: float
    unit: str | None = None
    source: str = 'manual'
    recorded_at: datetime | None = None

def _machine(db, machine_id, current):
    m = db.query(models.Machine).filter(models.Machine.id == machine_id, models.Machine.organization_id == current.organization_id, models.Machine.archived.is_(False)).first()
    if not m: raise HTTPException(404, 'machine not found')
    if current.role == models.UserRole.technician.value and not db.query(models.UserMachineAssignment).filter_by(user_id=current.id, machine_id=machine_id).first():
        raise HTTPException(404, 'machine not assigned to this worker')
    return m

def _component(db, component_id, current):
    c = db.query(models.Component).filter(models.Component.id == component_id).first()
    if not c: raise HTTPException(404, 'component not found')
    _machine(db, c.machine_id, current)
    return c

def _out(s):
    return {'id':s.id,'component_id':s.component_id,'name':s.name,'reading_type':s.reading_type,'unit':s.unit,'min_value':s.min_value,'max_value':s.max_value,'enabled':s.enabled,'created_at':s.created_at}

@router.get('/components/{component_id}/sensors')
def list_sensors(component_id:int,current:CurrentUser=Depends(get_current_user),db:Session=Depends(get_db)):
    _component(db,component_id,current)
    return [_out(s) for s in db.query(ComponentSensor).filter_by(component_id=component_id).order_by(ComponentSensor.id.asc()).all()]

@router.post('/components/{component_id}/sensors')
def create_sensor(component_id:int,payload:SensorIn,current:CurrentUser=Depends(get_current_user),db:Session=Depends(get_db)):
    if current.role != models.UserRole.admin.value: raise HTTPException(403,'administrator access required')
    _component(db,component_id,current)
    if not payload.name.strip() or not payload.reading_type.strip(): raise HTTPException(400,'sensor name and reading type are required')
    s=ComponentSensor(component_id=component_id,**payload.model_dump()); db.add(s); db.commit(); db.refresh(s); return _out(s)

@router.get('/components/{component_id}/readings')
def list_readings(component_id:int,limit:int=100,current:CurrentUser=Depends(get_current_user),db:Session=Depends(get_db)):
    _component(db,component_id,current)
    rows=db.query(ComponentSensorReading).filter_by(component_id=component_id).order_by(ComponentSensorReading.recorded_at.desc(),ComponentSensorReading.id.desc()).limit(max(1,min(limit,500))).all()
    return [{'id':r.id,'sensor_id':r.sensor_id,'component_id':r.component_id,'reading_type':r.reading_type,'value':r.value,'unit':r.unit,'source':r.source,'recorded_at':r.recorded_at} for r in rows]

@router.post('/components/{component_id}/readings')
def create_reading(component_id:int,payload:ReadingIn,current:CurrentUser=Depends(get_current_user),db:Session=Depends(get_db)):
    if current.role != models.UserRole.admin.value: raise HTTPException(403,'administrator access required')
    _component(db,component_id,current)
    s=db.query(ComponentSensor).filter_by(id=payload.sensor_id,component_id=component_id).first()
    if not s: raise HTTPException(404,'sensor not found for component')
    if not s.enabled: raise HTTPException(409,'sensor is disabled')
    if s.min_value is not None and payload.value < s.min_value: raise HTTPException(400,f'value is below sensor minimum ({s.min_value})')
    if s.max_value is not None and payload.value > s.max_value: raise HTTPException(400,f'value is above sensor maximum ({s.max_value})')
    r=ComponentSensorReading(sensor_id=s.id,component_id=component_id,reading_type=s.reading_type,value=payload.value,unit=payload.unit or s.unit,source=payload.source,recorded_at=payload.recorded_at or datetime.utcnow())
    db.add(r); db.commit(); db.refresh(r)
    return {'id':r.id,'sensor_id':r.sensor_id,'component_id':r.component_id,'reading_type':r.reading_type,'value':r.value,'unit':r.unit,'source':r.source,'recorded_at':r.recorded_at}
