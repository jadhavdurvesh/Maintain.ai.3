from sqlalchemy.orm import Session

from . import models


def log_event(db: Session, entity_type: str, entity_id, action: str, description: str, performed_by: str = None, organization_id: int | None = None):
    """Writes one permanent audit row. Never updated, never deleted by the app
    itself — call this alongside (not instead of) the normal DB write."""
    if organization_id is None:
        if entity_type == "organization":
            organization_id = int(entity_id) if entity_id is not None else 1
        elif entity_type == "user" and entity_id is not None:
            row = db.get(models.User, entity_id)
            organization_id = row.organization_id if row else None
        elif entity_id is not None:
            model_by_type = {
                "machine": models.Machine,
                "maintenance": models.MaintenanceRecord,
                "work_order": models.WorkOrder,
                "fault": models.FaultRecord,
                "alert": models.Alert,
                "component": models.Component,
            }
            entity_model = model_by_type.get(entity_type)
            row = db.get(entity_model, entity_id) if entity_model else None
            organization_id = getattr(getattr(row, "machine", None), "organization_id", None) or (
                row.organization_id if row is not None and hasattr(row, "organization_id") else None
            )
    if organization_id is None:
        raise ValueError(f"Cannot determine organization for audit event: {entity_type}#{entity_id}")
    entry = models.AuditLog(
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        description=description,
        performed_by=performed_by,
    )
    db.add(entry)
    db.commit()
