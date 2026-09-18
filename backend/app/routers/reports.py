import csv
import io
import json
import zipfile
from collections import Counter
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user, CurrentUser
from ..exports.pdf_report import build_pdf_report
from ..exports.excel_report import build_excel_report

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/dashboard", response_model=schemas.DashboardSummary)
def dashboard_summary(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    machines = db.query(models.Machine).filter_by(archived=False, organization_id=current.organization_id).all()
    machine_ids = [m.id for m in machines]
    return schemas.DashboardSummary(
        total_machines=len(machines),
        healthy=sum(1 for m in machines if m.status == models.HealthStatus.healthy),
        attention=sum(1 for m in machines if m.status == models.HealthStatus.attention),
        critical=sum(1 for m in machines if m.status == models.HealthStatus.critical),
        open_work_orders=db.query(models.WorkOrder)
            .filter(models.WorkOrder.machine_id.in_(machine_ids), models.WorkOrder.status != models.WorkOrderStatus.completed).count(),
        upcoming_maintenance=db.query(models.MaintenanceRecord)
            .filter(models.MaintenanceRecord.machine_id.in_(machine_ids), models.MaintenanceRecord.status == models.MaintenanceStatus.scheduled).count(),
        active_alerts=db.query(models.Alert)
            .filter(models.Alert.machine_id.in_(machine_ids), models.Alert.resolved == False).count(),  # noqa: E712
    )


@router.get("/reliability")
def reliability_report(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Failure counts and completion stats per machine — feeds the
    'Most Frequently Failing Machines' and 'Maintenance Completion Rate' dashboard sections."""
    machines = db.query(models.Machine).filter_by(archived=False, organization_id=current.organization_id).all()
    rows = []
    for m in machines:
        faults = db.query(models.FaultRecord).filter_by(machine_id=m.id).count()
        records = db.query(models.MaintenanceRecord).filter_by(machine_id=m.id).all()
        completed = sum(1 for r in records if r.status == models.MaintenanceStatus.completed)
        rows.append({
            "machine_id": m.id,
            "machine_code": m.machine_code,
            "name": m.name,
            "fault_count": faults,
            "maintenance_total": len(records),
            "maintenance_completed": completed,
            "completion_rate": round(completed / len(records) * 100, 1) if records else None,
            "health_score": m.health_score,
        })
    return sorted(rows, key=lambda r: r["fault_count"], reverse=True)


@router.get("/failure-analysis")
def failure_analysis(db: Session = Depends(get_db)):
    faults = db.query(models.FaultRecord).all()
    cause_counts = Counter((f.cause or "unspecified") for f in faults)
    return {
        "total_faults": len(faults),
        "most_common_causes": cause_counts.most_common(10),
    }


@router.get("/recent-faults")
def recent_faults(limit: int = 6, db: Session = Depends(get_db)):
    faults = (
        db.query(models.FaultRecord)
        .order_by(models.FaultRecord.reported_date.desc())
        .limit(limit)
        .all()
    )
    machines = {m.id: m for m in db.query(models.Machine).all()}
    return [
        {
            "id": f.id,
            "machine_name": machines[f.machine_id].name if f.machine_id in machines else "Unknown",
            "description": f.description,
            "cause": f.cause,
            "severity": f.severity,
            "reported_date": f.reported_date,
            "resolved": f.resolved_date is not None,
        }
        for f in faults
    ]


@router.get("/recent-activity")
def recent_activity(limit: int = 6, db: Session = Depends(get_db)):
    """Recently completed work orders and maintenance — the spec's
    'Recent Technician Activities' dashboard section."""
    machines = {m.id: m for m in db.query(models.Machine).all()}
    events = []

    completed_wos = (
        db.query(models.WorkOrder)
        .filter(models.WorkOrder.status == models.WorkOrderStatus.completed)
        .order_by(models.WorkOrder.completed_at.desc())
        .limit(limit)
        .all()
    )
    for wo in completed_wos:
        events.append({
            "type": "work_order",
            "machine_name": machines[wo.machine_id].name if wo.machine_id in machines else "Unknown",
            "description": f"Work order resolved: {wo.problem}",
            "performed_by": wo.assigned_to,
            "timestamp": wo.completed_at,
        })

    completed_maint = (
        db.query(models.MaintenanceRecord)
        .filter(models.MaintenanceRecord.status == models.MaintenanceStatus.completed)
        .order_by(models.MaintenanceRecord.completed_date.desc())
        .limit(limit)
        .all()
    )
    for r in completed_maint:
        events.append({
            "type": "maintenance",
            "machine_name": machines[r.machine_id].name if r.machine_id in machines else "Unknown",
            "description": f"{r.type.value.title()} maintenance: {r.description or r.type.value}",
            "performed_by": r.performed_by,
            "timestamp": r.completed_date,
        })

    events.sort(key=lambda e: e["timestamp"] or datetime.min, reverse=True)
    return events[:limit]




def _enum_value(value):
    return getattr(value, "value", value)


def _csv_bytes(headers, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def _machine_map(db):
    return {m.id: m for m in db.query(models.Machine).all()}


def _export_dataset(db, dataset):
    machines = _machine_map(db)
    if dataset == "machines":
        return ["id","machine_code","name","category","manufacturer","model_number","location","department","operating_hours","health_score","status","criticality","iot_enabled","archived"], [
            [m.id,m.machine_code,m.name,m.category,m.manufacturer,m.model_number,m.location,m.department,m.operating_hours,m.health_score,_enum_value(m.status),_enum_value(m.criticality),m.iot_enabled,m.archived] for m in machines.values()
        ]
    if dataset == "workorders":
        rows=db.query(models.WorkOrder).all()
        return ["id","machine_id","machine_code","machine_name","fault_id","problem","priority","status","recommended_actions","assigned_to","created_at","completed_at","resolution_notes"], [
            [w.id,w.machine_id,machines.get(w.machine_id).machine_code if w.machine_id in machines else "",machines.get(w.machine_id).name if w.machine_id in machines else "",w.fault_id,w.problem,_enum_value(w.priority),_enum_value(w.status),w.recommended_actions,w.assigned_to,w.created_at,w.completed_at,w.resolution_notes] for w in rows
        ]
    if dataset == "maintenance":
        rows=db.query(models.MaintenanceRecord).all()
        return ["id","machine_id","machine_code","machine_name","type","description","scheduled_date","completed_date","status","performed_by","notes"], [
            [r.id,r.machine_id,machines.get(r.machine_id).machine_code if r.machine_id in machines else "",machines.get(r.machine_id).name if r.machine_id in machines else "",_enum_value(r.type),r.description,r.scheduled_date,r.completed_date,_enum_value(r.status),r.performed_by,r.notes] for r in rows
        ]
    if dataset == "faults":
        rows=db.query(models.FaultRecord).all()
        return ["id","machine_id","machine_code","machine_name","description","symptoms","cause","resolution","severity","reported_date","resolved_date"], [
            [f.id,f.machine_id,machines.get(f.machine_id).machine_code if f.machine_id in machines else "",machines.get(f.machine_id).name if f.machine_id in machines else "",f.description,f.symptoms,f.cause,f.resolution,_enum_value(f.severity),f.reported_date,f.resolved_date] for f in rows
        ]
    if dataset == "alerts":
        rows=db.query(models.Alert).all()
        return ["id","machine_id","machine_code","machine_name","alert_type","severity","message","created_at","acknowledged","resolved"], [
            [a.id,a.machine_id,machines.get(a.machine_id).machine_code if a.machine_id in machines else "",machines.get(a.machine_id).name if a.machine_id in machines else "",a.alert_type,_enum_value(a.severity),a.message,a.created_at,a.acknowledged,a.resolved] for a in rows
        ]
    if dataset == "sensor_readings":
        rows=db.query(models.SensorReading).order_by(models.SensorReading.recorded_at.asc(),models.SensorReading.id.asc()).all()
        return ["id","machine_id","machine_code","machine_name","reading_type","value","unit","source","recorded_at"], [
            [s.id,s.machine_id,machines.get(s.machine_id).machine_code if s.machine_id in machines else "",machines.get(s.machine_id).name if s.machine_id in machines else "",s.reading_type,s.value,s.unit,s.source,s.recorded_at] for s in rows
        ]
    if dataset == "components":
        rows=db.query(models.Component).all()
        return ["id","machine_id","machine_code","machine_name","name","description"], [
            [x.id,x.machine_id,machines.get(x.machine_id).machine_code if x.machine_id in machines else "",machines.get(x.machine_id).name if x.machine_id in machines else "",x.name,x.description] for x in rows
        ]
    if dataset == "safety":
        rows=db.query(models.MachineSafetyPolicy).all()
        return ["id","machine_id","machine_code","machine_name","enabled","monitored_reading_type","unit","warning_low","warning_high","shutdown_low","shutdown_high","auto_shutdown_enabled","updated_at","last_trip_at","last_trip_value","last_trip_reason"], [
            [p.id,p.machine_id,machines.get(p.machine_id).machine_code if p.machine_id in machines else "",machines.get(p.machine_id).name if p.machine_id in machines else "",p.enabled,p.monitored_reading_type,p.unit,p.warning_low,p.warning_high,p.shutdown_low,p.shutdown_high,p.auto_shutdown_enabled,p.updated_at,p.last_trip_at,p.last_trip_value,p.last_trip_reason] for p in rows
        ]
    if dataset == "safety_events":
        rows=db.query(models.MachineSafetyEvent).order_by(models.MachineSafetyEvent.created_at.asc()).all()
        return ["id","machine_id","machine_code","machine_name","event_type","reading_type","value","threshold","message","shutdown_requested","device_acknowledged","created_at"], [
            [e.id,e.machine_id,machines.get(e.machine_id).machine_code if e.machine_id in machines else "",machines.get(e.machine_id).name if e.machine_id in machines else "",e.event_type,e.reading_type,e.value,e.threshold,e.message,e.shutdown_requested,e.device_acknowledged,e.created_at] for e in rows
        ]
    if dataset == "spare_parts":
        rows=db.query(models.SparePart).all()
        return ["id","name","part_number","description","quantity","minimum_stock","unit_cost"], [
            [x.id,x.name,x.part_number,x.description,x.quantity,x.minimum_stock,x.unit_cost] for x in rows
        ]
    if dataset == "notifications":
        rows=db.query(models.InAppNotification).all()
        return ["id","user_id","title","message","type","created_at","read"], [
            [x.id,x.user_id,x.title,x.message,x.type,x.created_at,x.read] for x in rows
        ]
    raise ValueError("Unknown export dataset")


@router.get("/export/csv")
def export_machines_csv(db: Session = Depends(get_db)):
    machines = db.query(models.Machine).filter_by(archived=False).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "machine_code", "name", "category", "location", "department",
        "operating_hours", "health_score", "status", "criticality",
    ])
    for m in machines:
        writer.writerow([
            m.machine_code, m.name, m.category, m.location, m.department,
            m.operating_hours, m.health_score, m.status, m.criticality,
        ])
    buffer.seek(0)
    filename = f"machines_export_{datetime.utcnow().date()}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/pdf")
def export_pdf(db: Session = Depends(get_db)):
    pdf_bytes = build_pdf_report(db)
    filename = f"maintain_ai_report_{datetime.utcnow().date()}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/excel")
def export_excel(db: Session = Depends(get_db)):
    xlsx_bytes = build_excel_report(db)
    filename = f"maintain_ai_report_{datetime.utcnow().date()}.xlsx"
    return StreamingResponse(
        iter([xlsx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )



@router.get("/export/gemini-pdf")
def export_gemini_pdf(db: Session = Depends(get_db)):
    """Generate a detailed, evidence-grounded PDF with Gemini narrative when configured."""
    machines = db.query(models.Machine).filter_by(archived=False).all()
    facts = []
    for m in machines:
        faults = db.query(models.FaultRecord).filter_by(machine_id=m.id).order_by(models.FaultRecord.reported_date.desc()).limit(10).all()
        work_orders = db.query(models.WorkOrder).filter_by(machine_id=m.id).order_by(models.WorkOrder.created_at.desc()).limit(10).all()
        maintenance = db.query(models.MaintenanceRecord).filter_by(machine_id=m.id).order_by(models.MaintenanceRecord.scheduled_date.desc()).limit(10).all()
        alerts = db.query(models.Alert).filter_by(machine_id=m.id).order_by(models.Alert.created_at.desc()).limit(10).all()
        readings = db.query(models.SensorReading).filter_by(machine_id=m.id).order_by(models.SensorReading.recorded_at.desc()).limit(100).all()
        facts.append({
            "machine": {"id":m.id,"code":m.machine_code,"name":m.name,"category":m.category,"location":m.location,"department":m.department,"health_score":m.health_score,"status":_enum_value(m.status),"criticality":_enum_value(m.criticality),"operating_hours":m.operating_hours},
            "faults":[{"id":x.id,"description":x.description,"cause":x.cause,"severity":_enum_value(x.severity),"reported_date":x.reported_date} for x in faults],
            "work_orders":[{"id":x.id,"problem":x.problem,"priority":_enum_value(x.priority),"status":_enum_value(x.status),"assigned_to":x.assigned_to,"created_at":x.created_at,"completed_at":x.completed_at,"resolution_notes":x.resolution_notes} for x in work_orders],
            "maintenance":[{"id":x.id,"type":_enum_value(x.type),"description":x.description,"status":_enum_value(x.status),"scheduled_date":x.scheduled_date,"completed_date":x.completed_date,"performed_by":x.performed_by,"notes":x.notes} for x in maintenance],
            "alerts":[{"id":x.id,"type":x.alert_type,"severity":_enum_value(x.severity),"message":x.message,"created_at":x.created_at,"acknowledged":x.acknowledged,"resolved":x.resolved} for x in alerts],
            "recent_readings":[{"type":x.reading_type,"value":x.value,"unit":x.unit,"recorded_at":x.recorded_at} for x in reversed(readings)],
        })

    ai = None
    try:
        from ..ai.gemini_client import diagnose_with_gemini
        ai = diagnose_with_gemini(
            "Create an executive and technician maintenance report from the supplied evidence. Summarize observed conditions, open actions, historical failures, maintenance status, telemetry observations, and safety items. Do not invent measurements or diagnoses.",
            {"report_scope":"all_machines","machines":facts},
            db=db,
        )
    except Exception:
        ai = None

    from ..exports.gemini_pdf_report import build_gemini_pdf_report
    pdf = build_gemini_pdf_report(db, facts, ai)
    filename = f"maintain_ai_gemini_report_{datetime.utcnow().date()}.pdf"
    return StreamingResponse(iter([pdf]), media_type="application/pdf", headers={"Content-Disposition":f"attachment; filename={filename}"})
@router.get("/export/{dataset}.csv")
def export_dataset_csv(dataset: str, db: Session = Depends(get_db)):
    allowed = {"machines","workorders","maintenance","faults","alerts","sensor_readings","components","safety","safety_events","spare_parts","notifications"}
    if dataset not in allowed:
        from fastapi import HTTPException
        raise HTTPException(404, "unknown export dataset")
    headers, rows = _export_dataset(db, dataset)
    filename = f"maintain_ai_{dataset}_{datetime.utcnow().date()}.csv"
    return StreamingResponse(iter([_csv_bytes(headers, rows)]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/export/all")
def export_all_data(db: Session = Depends(get_db)):
    allowed = ["machines","workorders","maintenance","faults","alerts","sensor_readings","components","safety","safety_events","spare_parts","notifications"]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        manifest = {"generated_at_utc": datetime.utcnow().isoformat() + "Z", "datasets": allowed}
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        for dataset in allowed:
            headers, rows = _export_dataset(db, dataset)
            archive.writestr(f"{dataset}.csv", _csv_bytes(headers, rows))
    buffer.seek(0)
    filename = f"maintain_ai_full_export_{datetime.utcnow().date()}.zip"
    return StreamingResponse(iter([buffer.getvalue()]), media_type="application/zip", headers={"Content-Disposition": f"attachment; filename={filename}"})


