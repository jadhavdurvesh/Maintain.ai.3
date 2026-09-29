from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from .. import models, schemas
from ..sensor_models import ComponentSensor, ComponentSensorReading
from ..database import get_db
from ..deps import get_current_user, CurrentUser

router = APIRouter(prefix="/api/components", tags=["component-sensors"])

def _component(db, component_id, current):
    row = db.query(models.Component).join(models.Machine).filter(models.Component.id == component_id, models.Machine.organization_id == current.organization_id).first()
    if not row: raise HTTPException(404, "component not found")
    return row

def _sensor(db, sensor_id, current):
    row = db.query(ComponentSensor).join(models.Component, ComponentSensor.component_id == models.Component.id).join(models.Machine, models.Component.machine_id == models.Machine.id).filter(ComponentSensor.id == sensor_id, models.Machine.organization_id == current.organization_id).first()
    if not row: raise HTTPException(404, "sensor not found")
    return row

class SensorIn(schemas.BaseModel):
    name: str
    reading_type: str
    unit: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    enabled: bool = True
class SensorOut(SensorIn):
    id: int; component_id: int; created_at: datetime
    model_config = schemas.ConfigDict(from_attributes=True)
class ReadingIn(schemas.BaseModel):
    sensor_id: int
    reading_type: str
    value: float
    unit: str | None = None
    source: str = "manual"
class ReadingOut(ReadingIn):
    id: int; component_id: int; recorded_at: datetime
    model_config = schemas.ConfigDict(from_attributes=True)

@router.get("/{component_id}/sensors", response_model=List[SensorOut])
def list_sensors(component_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _component(db, component_id, current)
    return db.query(ComponentSensor).filter(ComponentSensor.component_id == component_id).order_by(ComponentSensor.id.asc()).all()

@router.post("/{component_id}/sensors", response_model=SensorOut)
def add_sensor(component_id: int, payload: SensorIn, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if current.role != models.UserRole.admin.value: raise HTTPException(403, "administrator access required")
    _component(db, component_id, current)
    sensor = ComponentSensor(component_id=component_id, **payload.model_dump())
    db.add(sensor); db.commit(); db.refresh(sensor); return sensor

@router.patch("/sensors/{sensor_id}", response_model=SensorOut)
def update_sensor(sensor_id: int, payload: SensorIn, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if current.role != models.UserRole.admin.value: raise HTTPException(403, "administrator access required")
    sensor = _sensor(db, sensor_id, current)
    for k,v in payload.model_dump().items(): setattr(sensor,k,v)
    db.commit(); db.refresh(sensor); return sensor

@router.delete("/sensors/{sensor_id}")
def delete_sensor(sensor_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if current.role != models.UserRole.admin.value: raise HTTPException(403, "administrator access required")
    sensor = _sensor(db, sensor_id, current); db.delete(sensor); db.commit(); return {"deleted": True}

@router.get("/{component_id}/readings", response_model=List[ReadingOut])
def list_readings(component_id: int, limit: int = Query(40, ge=1, le=200), current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _component(db, component_id, current)
    return db.query(ComponentSensorReading).filter(ComponentSensorReading.component_id == component_id).order_by(ComponentSensorReading.recorded_at.desc(), ComponentSensorReading.id.desc()).limit(limit).all()

@router.post("/{component_id}/readings", response_model=ReadingOut)
def add_reading(component_id: int, payload: ReadingIn, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if current.role != models.UserRole.admin.value: raise HTTPException(403, "administrator access required")
    _component(db, component_id, current); sensor = _sensor(db, payload.sensor_id, current)
    if sensor.component_id != component_id: raise HTTPException(400, "sensor does not belong to component")
    row = ComponentSensorReading(component_id=component_id, **payload.model_dump())
    db.add(row); db.commit(); db.refresh(row); return row
