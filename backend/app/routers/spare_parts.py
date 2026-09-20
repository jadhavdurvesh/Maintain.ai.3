from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user, CurrentUser

router = APIRouter(prefix="/api/spare-parts", tags=["spare_parts"])


@router.get("", response_model=List[schemas.SparePartOut])
def list_parts(low_stock_only: bool = False, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    parts = db.query(models.SparePart).filter(models.SparePart.organization_id == current.organization_id).all()
    if low_stock_only:
        parts = [p for p in parts if p.quantity <= p.minimum_stock]
    return parts


@router.post("", response_model=schemas.SparePartOut)
def create_part(payload: schemas.SparePartIn, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if db.query(models.SparePart).filter(models.SparePart.part_number == payload.part_number, models.SparePart.organization_id == current.organization_id).first():
        raise HTTPException(400, "part_number already exists")
    part = models.SparePart(**payload.model_dump(), organization_id=current.organization_id)
    db.add(part)
    db.commit()
    db.refresh(part)
    return part


@router.patch("/{part_id}", response_model=schemas.SparePartOut)
def update_part(part_id: int, quantity: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    part = db.query(models.SparePart).filter(models.SparePart.id == part_id, models.SparePart.organization_id == current.organization_id).first()
    if not part:
        raise HTTPException(404, "part not found")
    part.quantity = quantity
    db.commit()
    db.refresh(part)
    return part
