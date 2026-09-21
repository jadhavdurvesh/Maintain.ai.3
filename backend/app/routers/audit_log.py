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
    if current.role == models.UserRole.technician.value:
        visible_ids = [row[0] for row in db.query(models.Machine.id).join(models.UserMachineAssignment, models.UserMachineAssignment.machine_id == models.Machine.id).filter(models.Machine.organization_id == current.organization_id, models.UserMachineAssignment.user_id == current.id).all()]
        q = q.filter(
            ((models.AuditLog.entity_type == "machine") & models.AuditLog.entity_id.in_(visible_ids))
            | (models.AuditLog.entity_type.in_(["maintenance", "work_order", "fault", "alert", "component"]) & models.AuditLog.entity_id.in_(
                db.query(models.MaintenanceRecord.id).filter(models.MaintenanceRecord.machine_id.in_(visible_ids))
            ))
        )
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
