"""Durable Lab-branch anomaly event creation.

Keeps anomaly evidence separate from generic machine alerts so the R&D
pipeline can later drive notification, acknowledgement, and model evaluation.
"""
import json
from sqlalchemy.orm import Session
from .. import models


def create_anomaly_event(db: Session, machine: models.Machine, behaviour: dict, message: str):
    if not behaviour.get("available") or not behaviour.get("persistent_change"):
        return None

    score = float(behaviour.get("anomaly_score") or 0.0)
    severity = (
        models.AlertSeverity.critical if score >= 0.80
        else models.AlertSeverity.high if score >= 0.60
        else models.AlertSeverity.warning
    )

    recent = (
        db.query(models.MLAnomalyEvent)
        .filter(
            models.MLAnomalyEvent.machine_id == machine.id,
            models.MLAnomalyEvent.reading_type == behaviour.get("reading_type"),
            models.MLAnomalyEvent.resolved.is_(False),
        )
        .order_by(models.MLAnomalyEvent.created_at.desc())
        .first()
    )
    if recent:
        if recent.anomaly_score < score:
            recent.anomaly_score = score
            recent.evidence_json = json.dumps(behaviour, separators=(",", ":"))
            db.commit()
        return recent

    event = models.MLAnomalyEvent(
        machine_id=machine.id,
        reading_type=behaviour.get("reading_type") or "unknown",
        anomaly_score=score,
        severity=severity,
        message=message,
        evidence_json=json.dumps(behaviour, separators=(",", ":")),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
