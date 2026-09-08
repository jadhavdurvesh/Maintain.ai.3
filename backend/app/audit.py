from sqlalchemy.orm import Session

from . import models


def log_event(db: Session, entity_type: str, entity_id, action: str, description: str, performed_by: str = None):
    """Writes one permanent audit row. Never updated, never deleted by the app
    itself — call this alongside (not instead of) the normal DB write."""
    entry = models.AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        description=description,
        performed_by=performed_by,
    )
    db.add(entry)
    db.commit()
