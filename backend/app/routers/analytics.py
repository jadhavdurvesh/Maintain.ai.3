from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..ml import model as risk_model
from ..ml.online import score_machine
from .. import models

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/model-status")
def get_model_status(db: Session = Depends(get_db)):
    return risk_model.model_status(db)


@router.post("/train")
def train_model(db: Session = Depends(get_db)):
    return risk_model.train(db)


@router.get("/risk-predictions")
def get_risk_predictions(db: Session = Depends(get_db)):
    return risk_model.predict_risk(db)


@router.get("/machines/{machine_id}/behaviour")
def get_machine_behaviour(machine_id: int, db: Session = Depends(get_db)):
    """Return the Lab online learner's current behavioural evidence."""
    if db.get(models.Machine, machine_id) is None:
        raise HTTPException(404, "machine not found")
    return score_machine(db, machine_id)
