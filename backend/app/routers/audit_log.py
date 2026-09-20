from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import get_current_user, CurrentUser

router = APIRouter(prefix="/api/audit-log", tags=["audit_log"])


@router.get("")
def list_audit_log(
    entity_type: str | None = None,
    limit: int = 100,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(models.AuditLog).filter(models.AuditLog.organization_id == current.organization_id)
    if entity_type:
        q = q.filter_by(entity_type=entity_type)
    entries = q.order_by(models.AuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": e.id,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "action": e.action,
            "description": e.description,
            "performed_by": e.performed_by,
            "created_at": e.created_at,
        }
        for e in entries
    ]


@router.get("/count")
def audit_log_count(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"total_events": db.query(models.AuditLog).filter(models.AuditLog.organization_id == current.organization_id).count()}
