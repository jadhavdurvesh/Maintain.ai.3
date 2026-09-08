from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..ml import model as risk_model

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
