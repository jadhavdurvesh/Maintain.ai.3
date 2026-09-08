from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, audit
from ..database import get_db
from ..deps import get_current_user, CurrentUser

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=List[schemas.AlertOut])
def list_alerts(
    active_only: bool = True,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (
        db.query(models.Alert)
        .join(models.Machine)
        .filter(models.Machine.organization_id == current.organization_id)
    )
    if active_only:
        q = q.filter(models.Alert.resolved == False)  # noqa: E712
    return q.order_by(models.Alert.created_at.desc()).all()


@router.post("/{alert_id}/acknowledge", response_model=schemas.AlertOut)
def acknowledge_alert(alert_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    alert = db.get(models.Alert, alert_id)
    if not alert or alert.machine.organization_id != current.organization_id:
        raise HTTPException(404, "alert not found")
    alert.acknowledged = True
    db.commit()
    db.refresh(alert)
    audit.log_event(db, "alert", alert.id, "acknowledged", f"Alert acknowledged: {alert.message}")
    return alert


@router.post("/{alert_id}/resolve", response_model=schemas.AlertOut)
def resolve_alert(alert_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    alert = db.get(models.Alert, alert_id)
    if not alert or alert.machine.organization_id != current.organization_id:
        raise HTTPException(404, "alert not found")
    alert.resolved = True
    db.commit()
    db.refresh(alert)
    audit.log_event(db, "alert", alert.id, "resolved", f"Alert resolved: {alert.message}")
    return alert
