import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..ai import offline_engine, gemini_client

router = APIRouter(prefix="/api/ai", tags=["ai_assistant"])


def _machine_context(db: Session, machine: models.Machine | None) -> dict | None:
    """Build a compact evidence pack for the selected asset."""
    if not machine:
        return None

    readings = (
        db.query(models.SensorReading)
        .filter_by(machine_id=machine.id)
        .order_by(models.SensorReading.recorded_at.desc())
        .limit(30)
        .all()
    )
    grouped: dict[str, list[models.SensorReading]] = {}
    for reading in readings:
        grouped.setdefault((reading.reading_type or "unknown").lower(), []).append(reading)

    sensor_summary = {}
    for kind, items in grouped.items():
        values = [float(item.value) for item in items]
        latest = items[0]
        sensor_summary[kind] = {
            "latest": latest.value,
            "unit": latest.unit,
            "average": round(sum(values) / len(values), 2),
            "minimum": min(values),
            "maximum": max(values),
            "samples": len(values),
            "latest_recorded_at": latest.recorded_at.isoformat() if latest.recorded_at else None,
        }

    faults = (
        db.query(models.FaultRecord)
        .filter_by(machine_id=machine.id)
        .order_by(models.FaultRecord.reported_date.desc())
        .limit(5)
        .all()
    )
    maintenance = (
        db.query(models.MaintenanceRecord)
        .filter_by(machine_id=machine.id)
        .order_by(models.MaintenanceRecord.completed_date.desc().nullslast())
        .limit(5)
        .all()
    )
    alerts = (
        db.query(models.Alert)
        .filter_by(machine_id=machine.id)
        .order_by(models.Alert.created_at.desc())
        .limit(5)
        .all()
    )

    return {
        "asset": {
            "id": machine.id,
            "name": machine.name,
            "category": machine.category,
            "manufacturer": machine.manufacturer,
            "model_number": machine.model_number,
            "location": machine.location,
            "department": machine.department,
            "operating_hours": machine.operating_hours,
            "criticality": machine.criticality.value if hasattr(machine.criticality, "value") else str(machine.criticality),
            "health_score": machine.health_score,
            "status": machine.status.value if hasattr(machine.status, "value") else str(machine.status),
            "iot_enabled": machine.iot_enabled,
        },
        "sensor_summary": sensor_summary,
        "recent_faults": [
            {
                "description": f.description,
                "symptoms": f.symptoms,
                "cause": f.cause,
                "resolution": f.resolution,
                "severity": f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                "reported_date": f.reported_date.isoformat() if f.reported_date else None,
                "resolved": f.resolved_date is not None,
            }
            for f in faults
        ],
        "recent_maintenance": [
            {
                "type": r.type.value if hasattr(r.type, "value") else str(r.type),
                "description": r.description,
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "completed_date": r.completed_date.isoformat() if r.completed_date else None,
                "notes": r.notes,
            }
            for r in maintenance
        ],
        "recent_alerts": [
            {
                "type": a.alert_type,
                "severity": a.severity.value if hasattr(a.severity, "value") else str(a.severity),
                "message": a.message,
                "resolved": a.resolved,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts
        ],
    }


@router.post("/diagnose", response_model=schemas.DiagnoseResponse)
def diagnose(payload: schemas.DiagnoseRequest, db: Session = Depends(get_db)):
    machine = db.get(models.Machine, payload.machine_id) if payload.machine_id else None
    machine_category = machine.category if machine else None

    result = None
    if payload.use_online_ai:
        result = gemini_client.diagnose_with_gemini(
            payload.problem_description,
            _machine_context(db, machine),
            payload.answers,
            db=db,
        )

    if result is None:
        result = offline_engine.diagnose(
            db, machine_category, payload.problem_description, payload.answers
        )

    session = models.AIDiagnosticSession(
        machine_id=payload.machine_id,
        problem_description=payload.problem_description,
        questions_asked=json.dumps(result.get("clarifying_questions", [])),
        answers=json.dumps(payload.answers or []),
        likely_causes=json.dumps(result.get("possible_causes", [])),
        recommended_action="; ".join(result.get("recommended_procedure", [])),
        source=result.get("source", "offline"),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return schemas.DiagnoseResponse(
        session_id=session.id,
        safety_notice=result.get("safety_notice", offline_engine.SAFETY_NOTICE),
        clarifying_questions=result.get("clarifying_questions", []),
        possible_causes=result.get("possible_causes", []),
        recommended_procedure=result.get("recommended_procedure", []),
        source=result.get("source", "offline"),
        needs_more_info=result.get("needs_more_info", False),
    )


@router.post("/sessions/{session_id}/outcome")
def record_outcome(session_id: int, final_technician_result: str, db: Session = Depends(get_db)):
    session = db.get(models.AIDiagnosticSession, session_id)
    if not session:
        raise HTTPException(404, "session not found")
    session.final_technician_result = final_technician_result
    db.commit()
    return {"updated": True}


@router.get("/sessions")
def list_sessions(machine_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(models.AIDiagnosticSession)
    if machine_id:
        q = q.filter_by(machine_id=machine_id)
    sessions = q.order_by(models.AIDiagnosticSession.created_at.desc()).all()
    return [
        {
            "id": s.id,
            "machine_id": s.machine_id,
            "problem_description": s.problem_description,
            "likely_causes": json.loads(s.likely_causes or "[]"),
            "recommended_action": s.recommended_action,
            "final_technician_result": s.final_technician_result,
            "source": s.source,
            "created_at": s.created_at,
        }
        for s in sessions
    ]
