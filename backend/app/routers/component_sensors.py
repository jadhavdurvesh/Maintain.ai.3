from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas
from ..sensor_models import ComponentSensor
from ..database import get_db
from ..deps import get_current_user, CurrentUser

router = APIRouter(prefix="/api/components", tags=["component-sensors"])

def _component(db, component_id, current):
    row = db.query(models.Component).join(models.Machine).filter(models.Component.id == component_id, models.Machine.organization_id == current.organization_id).first()
    if not row: raise HTTPException(404, "component not found")
    return row

class SensorIn(schemas.BaseModel):
    name: str
    reading_type: str
    unit: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    enabled: bool = True

class SensorOut(SensorIn):
    id: int
    component_id: int
    created_at: schemas.datetime
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
    db.add(sensor); db.commit(); db.refresh(sensor)
    return sensor

@router.patch("/sensors/{sensor_id}", response_model=SensorOut)
def update_sensor(sensor_id: int, payload: SensorIn, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if current.role != models.UserRole.admin.value: raise HTTPException(403, "administrator access required")
    sensor = db.query(ComponentSensor).join(models.Component).join(models.Machine).filter(ComponentSensor.id == sensor_id, models.Machine.organization_id == current.organization_id).first()
    if not sensor: raise HTTPException(404, "sensor not found")
    for k,v in payload.model_dump().items(): setattr(sensor,k,v)
    db.commit(); db.refresh(sensor); return sensor

@router.delete("/sensors/{sensor_id}")
def delete_sensor(sensor_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if current.role != models.UserRole.admin.value: raise HTTPException(403, "administrator access required")
    sensor = db.query(ComponentSensor).join(models.Component).join(models.Machine).filter(ComponentSensor.id == sensor_id, models.Machine.organization_id == current.organization_id).first()
    if not sensor: raise HTTPException(404, "sensor not found")
    db.delete(sensor); db.commit(); return {"deleted": True}
