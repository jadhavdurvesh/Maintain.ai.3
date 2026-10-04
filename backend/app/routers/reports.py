import csv
import io
import json
import zipfile
from collections import Counter
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user, CurrentUser
from ..exports.pdf_report import build_pdf_report
from ..exports.excel_report import build_excel_report
from ..ml.forecast_runs import MLForecastRun

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _require_admin(current: CurrentUser):
    if current.role != models.UserRole.admin.value:
        raise HTTPException(403, "administrator access required")


def _visible_machines(db: Session, current: CurrentUser):
    query = db.query(models.Machine).filter(
        models.Machine.archived.is_(False),
        models.Machine.organization_id == current.organization_id,
    )
    if current.id is not None and current.role == models.UserRole.technician.value:
        query = query.join(
            models.UserMachineAssignment,
            models.UserMachineAssignment.machine_id == models.Machine.id,
        ).filter(models.UserMachineAssignment.user_id == current.id)
    return query.all()


@router.get("/dashboard", response_model=schemas.DashboardSummary)
def dashboard_summary(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    machines = _visible_machines(db, current)
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
    machines = _visible_machines(db, current)
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
def failure_analysis(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    faults = db.query(models.FaultRecord).join(models.Machine).filter(models.Machine.id.in_([m.id for m in _visible_machines(db, current)])).all()
    cause_counts = Counter((f.cause or "unspecified") for f in faults)
    return {
        "total_faults": len(faults),
        "most_common_causes": cause_counts.most_common(10),
    }


@router.get("/recent-faults")
def recent_faults(limit: int = 6, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    visible_ids = [m.id for m in _visible_machines(db, current)]
    faults = (
        db.query(models.FaultRecord).join(models.Machine).filter(models.Machine.id.in_(visible_ids))
        .order_by(models.FaultRecord.reported_date.desc())
        .limit(limit)
        .all()
    )
    machines = {m.id: m for m in _visible_machines(db, current)}
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
def recent_activity(limit: int = 6, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Recently completed work orders and maintenance — the spec's
    'Recent Technician Activities' dashboard section."""
    visible_ids = [m.id for m in _visible_machines(db, current)]
    machines = {m.id: m for m in _visible_machines(db, current)}
    events = []

    completed_wos = (
        db.query(models.WorkOrder).join(models.Machine).filter(models.Machine.id.in_(visible_ids), models.WorkOrder.status == models.WorkOrderStatus.completed)
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
        db.query(models.MaintenanceRecord).join(models.Machine).filter(models.MaintenanceRecord.machine_id.in_(visible_ids), models.MaintenanceRecord.status == models.MaintenanceStatus.completed)
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


def _machine_map(db, current: CurrentUser | None = None):
    query = db.query(models.Machine).filter(models.Machine.archived.is_(False))
    if current is not None:
        query = query.filter(models.Machine.organization_id == current.organization_id)
        if current.id is not None and current.role == models.UserRole.technician.value:
            query = query.join(models.UserMachineAssignment, models.UserMachineAssignment.machine_id == models.Machine.id).filter(models.UserMachineAssignment.user_id == current.id)
    return {m.id: m for m in query.all()}


def _export_dataset(db, dataset, current=None):
    machines = _machine_map(db, current)
    if dataset == "machines":
        return ["id","machine_code","name","category","manufacturer","model_number","location","department","operating_hours","health_score","status","criticality","iot_enabled","archived"], [
            [m.id,m.machine_code,m.name,m.category,m.manufacturer,m.model_number,m.location,m.department,m.operating_hours,m.health_score,_enum_value(m.status),_enum_value(m.criticality),m.iot_enabled,m.archived] for m in machines.values()
        ]
    if dataset == "workorders":
        rows=db.query(models.WorkOrder).filter(models.WorkOrder.machine_id.in_(machines.keys())).all()
        return ["id","machine_id","machine_code","machine_name","fault_id","problem","priority","status","recommended_actions","assigned_to","created_at","completed_at","resolution_notes"], [
            [w.id,w.machine_id,machines.get(w.machine_id).machine_code if w.machine_id in machines else "",machines.get(w.machine_id).name if w.machine_id in machines else "",w.fault_id,w.problem,_enum_value(w.priority),_enum_value(w.status),w.recommended_actions,w.assigned_to,w.created_at,w.completed_at,w.resolution_notes] for w in rows
        ]
    if dataset == "maintenance":
        rows=db.query(models.MaintenanceRecord).filter(models.MaintenanceRecord.machine_id.in_(machines.keys())).all()
        return ["id","machine_id","machine_code","machine_name","type","description","scheduled_date","completed_date","status","performed_by","notes"], [
            [r.id,r.machine_id,machines.get(r.machine_id).machine_code if r.machine_id in machines else "",machines.get(r.machine_id).name if r.machine_id in machines else "",_enum_value(r.type),r.description,r.scheduled_date,r.completed_date,_enum_value(r.status),r.performed_by,r.notes] for r in rows
        ]
    if dataset == "faults":
        rows=db.query(models.FaultRecord).filter(models.FaultRecord.machine_id.in_(machines.keys())).all()
        return ["id","machine_id","machine_code","machine_name","description","symptoms","cause","resolution","severity","reported_date","resolved_date"], [
            [f.id,f.machine_id,machines.get(f.machine_id).machine_code if f.machine_id in machines else "",machines.get(f.machine_id).name if f.machine_id in machines else "",f.description,f.symptoms,f.cause,f.resolution,_enum_value(f.severity),f.reported_date,f.resolved_date] for f in rows
        ]
    if dataset == "alerts":
        rows=db.query(models.Alert).filter(models.Alert.machine_id.in_(machines.keys())).all()
        return ["id","machine_id","machine_code","machine_name","alert_type","severity","message","created_at","acknowledged","resolved"], [
            [a.id,a.machine_id,machines.get(a.machine_id).machine_code if a.machine_id in machines else "",machines.get(a.machine_id).name if a.machine_id in machines else "",a.alert_type,_enum_value(a.severity),a.message,a.created_at,a.acknowledged,a.resolved] for a in rows
        ]
    if dataset == "sensor_readings":
        rows=db.query(models.SensorReading).filter(models.SensorReading.machine_id.in_(machines.keys())).order_by(models.SensorReading.recorded_at.asc(),models.SensorReading.id.asc()).all()
        return ["id","machine_id","machine_code","machine_name","reading_type","value","unit","source","recorded_at"], [
            [s.id,s.machine_id,machines.get(s.machine_id).machine_code if s.machine_id in machines else "",machines.get(s.machine_id).name if s.machine_id in machines else "",s.reading_type,s.value,s.unit,s.source,s.recorded_at] for s in rows
        ]
    if dataset == "components":
        rows=db.query(models.Component).filter(models.Component.machine_id.in_(machines.keys())).all()
        return ["id","machine_id","machine_code","machine_name","name","description"], [
            [x.id,x.machine_id,machines.get(x.machine_id).machine_code if x.machine_id in machines else "",machines.get(x.machine_id).name if x.machine_id in machines else "",x.name,x.description] for x in rows
        ]
    if dataset == "machine_performance":
        from ..performance import period_bounds
        profiles = {p.machine_id: p for p in db.query(models.MachinePerformanceProfile).all()}
        monthly = db.query(models.MachinePerformanceMonth).filter(
            models.MachinePerformanceMonth.machine_id.in_(machines.keys())
        ).order_by(models.MachinePerformanceMonth.month.desc()).all()
        rows = []
        for item in monthly:
            machine = machines.get(item.machine_id)
            if not machine:
                continue
            profile = profiles.get(item.machine_id)
            start, end = period_bounds(item.month)
            try:
                from .performance import _payload
                data = _payload(machine, profile, item, item.month, db)
            except Exception:
                data = {}
            rows.append([
                item.id, machine.id, machine.machine_code, machine.name, item.month,
                profile.started_on if profile else None,
                profile.rated_capacity if profile else None,
                profile.capacity_unit if profile else None,
                data.get("current_working_hours"), data.get("period_working_hours"),
                data.get("mtbf_hours"), data.get("mttr_minutes"),
                data.get("availability_percent"), data.get("performance_percent"),
                data.get("quality_percent"), data.get("oee_percent"),
                profile.oee_target if profile else None,
                item.planned_hours, item.manual_runtime_hours,
                item.total_units, item.good_units, item.rejected_units,
                item.ideal_cycle_seconds,
            ])
        return [
            "record_id","machine_id","machine_code","machine_name","month","started_on",
            "rated_capacity","capacity_unit","current_working_hours","period_working_hours",
            "mtbf_hours","mttr_minutes","availability_percent","performance_percent",
            "quality_percent","oee_percent","oee_target_percent","planned_hours",
            "manual_runtime_hours","total_units","good_units","rejected_units","ideal_cycle_seconds"
        ], rows
    if dataset == "safety":
        rows=db.query(models.MachineSafetyPolicy).filter(models.MachineSafetyPolicy.machine_id.in_(machines.keys())).all()
        return ["id","machine_id","machine_code","machine_name","enabled","monitored_reading_type","unit","warning_low","warning_high","shutdown_low","shutdown_high","auto_shutdown_enabled","updated_at","last_trip_at","last_trip_value","last_trip_reason"], [
            [p.id,p.machine_id,machines.get(p.machine_id).machine_code if p.machine_id in machines else "",machines.get(p.machine_id).name if p.machine_id in machines else "",p.enabled,p.monitored_reading_type,p.unit,p.warning_low,p.warning_high,p.shutdown_low,p.shutdown_high,p.auto_shutdown_enabled,p.updated_at,p.last_trip_at,p.last_trip_value,p.last_trip_reason] for p in rows
        ]
    if dataset == "safety_events":
        rows=db.query(models.MachineSafetyEvent).filter(models.MachineSafetyEvent.machine_id.in_(machines.keys())).order_by(models.MachineSafetyEvent.created_at.asc()).all()
        return ["id","machine_id","machine_code","machine_name","event_type","reading_type","value","threshold","message","shutdown_requested","device_acknowledged","created_at"], [
            [e.id,e.machine_id,machines.get(e.machine_id).machine_code if e.machine_id in machines else "",machines.get(e.machine_id).name if e.machine_id in machines else "",e.event_type,e.reading_type,e.value,e.threshold,e.message,e.shutdown_requested,e.device_acknowledged,e.created_at] for e in rows
        ]
    if dataset == "spare_parts":
        rows=db.query(models.SparePart).filter(models.SparePart.organization_id == current.organization_id).all()
        return ["id","name","part_number","description","quantity","minimum_stock","unit_cost"], [
            [x.id,x.name,x.part_number,x.description,x.quantity,x.minimum_stock,x.unit_cost] for x in rows
        ]
    if dataset == "notifications":
        rows=db.query(models.InAppNotification).join(models.User).filter(models.User.organization_id == current.organization_id).all()
        return ["id","user_id","title","message","type","created_at","read"], [
            [x.id,x.user_id,x.title,x.message,x.type,x.created_at,x.read] for x in rows
        ]
    raise ValueError("Unknown export dataset")


@router.get("/export/csv")
def export_machines_csv(db: Session = Depends(get_db), current: CurrentUser = Depends(get_current_user)):
    machines = _visible_machines(db, current)
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
def export_pdf(db: Session = Depends(get_db), current: CurrentUser = Depends(get_current_user)):
    _require_admin(current)
    pdf_bytes = build_pdf_report(db, organization_id=current.organization_id)
    filename = f"maintain_ai_report_{datetime.utcnow().date()}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/excel")
def export_excel(db: Session = Depends(get_db), current: CurrentUser = Depends(get_current_user)):
    _require_admin(current)
    xlsx_bytes = build_excel_report(db, organization_id=current.organization_id)
    filename = f"maintain_ai_report_{datetime.utcnow().date()}.xlsx"
    return StreamingResponse(
        iter([xlsx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )



@router.get("/export/ai-pdf")
def export_ai_pdf(db: Session = Depends(get_db), current: CurrentUser = Depends(get_current_user)):
    _require_admin(current)
    """Generate a detailed, evidence-grounded AI maintenance report."""
    machines = _visible_machines(db, current)
    facts = []
    for m in machines:
        faults = db.query(models.FaultRecord).filter_by(machine_id=m.id).order_by(models.FaultRecord.reported_date.desc()).limit(10).all()
        work_orders = db.query(models.WorkOrder).filter_by(machine_id=m.id).order_by(models.WorkOrder.created_at.desc()).limit(10).all()
        maintenance = db.query(models.MaintenanceRecord).filter_by(machine_id=m.id).order_by(models.MaintenanceRecord.scheduled_date.desc()).limit(10).all()
        alerts = db.query(models.Alert).filter_by(machine_id=m.id).order_by(models.Alert.created_at.desc()).limit(10).all()
        # Report only the latest telemetry sample for each signal. Historical readings
        # remain available through the dedicated sensor_readings CSV/ZIP export.
        reading_rows = db.query(models.SensorReading).filter_by(machine_id=m.id).order_by(models.SensorReading.recorded_at.desc(), models.SensorReading.id.desc()).all()
        latest_by_type = {}
        for reading in reading_rows:
            if reading.reading_type not in latest_by_type:
                latest_by_type[reading.reading_type] = reading
        readings = list(latest_by_type.values())
        facts.append({
            "machine": {"id":m.id,"code":m.machine_code,"name":m.name,"category":m.category,"location":m.location,"department":m.department,"health_score":m.health_score,"status":_enum_value(m.status),"criticality":_enum_value(m.criticality),"operating_hours":m.operating_hours},
            "faults":[{"id":x.id,"description":x.description,"cause":x.cause,"severity":_enum_value(x.severity),"reported_date":x.reported_date} for x in faults],
            "work_orders":[{"id":x.id,"problem":x.problem,"priority":_enum_value(x.priority),"status":_enum_value(x.status),"assigned_to":x.assigned_to,"created_at":x.created_at,"completed_at":x.completed_at,"resolution_notes":x.resolution_notes} for x in work_orders],
            "maintenance":[{"id":x.id,"type":_enum_value(x.type),"description":x.description,"status":_enum_value(x.status),"scheduled_date":x.scheduled_date,"completed_date":x.completed_date,"performed_by":x.performed_by,"notes":x.notes} for x in maintenance],
            "alerts":[{"id":x.id,"type":x.alert_type,"severity":_enum_value(x.severity),"message":x.message,"created_at":x.created_at,"acknowledged":x.acknowledged,"resolved":x.resolved} for x in alerts],
            "recent_readings":[{"type":x.reading_type,"value":x.value,"unit":x.unit,"recorded_at":x.recorded_at} for x in sorted(readings, key=lambda r: (r.reading_type or ""))],
        })

    ai = None
    try:
        from ..ai.gemini_client import diagnose_with_gemini
        ai = diagnose_with_gemini(
            "Create an executive and technician maintenance report from the supplied evidence. Summarize observed conditions, open actions, historical failures, maintenance status, telemetry observations, and safety items. Do not invent measurements or diagnoses.",
            {"report_scope":"all_machines","machines":facts},
            db=db, organization_id=current.organization_id,
        )
    except Exception:
        ai = None

    from ..exports.gemini_pdf_report import build_gemini_pdf_report
    pdf = build_gemini_pdf_report(db, facts, ai)
    filename = f"maintain_ai_ai_report_{datetime.utcnow().date()}.pdf"
    return StreamingResponse(iter([pdf]), media_type="application/pdf", headers={"Content-Disposition":f"attachment; filename={filename}"})
@router.get("/export/prediction-pdf")
def export_prediction_pdf(
    machine_id: int,
    reading_type: str = "temperature",
    model: str = "chronos-bolt-tiny",
    horizon: int = 12,
    run_id: int | None = None,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    """Export one saved Model Lab prediction with its observed-vs-forecast chart."""
    machines = _machine_map(db, current)
    machine = machines.get(machine_id)
    if not machine:
        raise HTTPException(404, "machine not found")

    query = db.query(MLForecastRun).filter(
        MLForecastRun.machine_id == machine_id,
        MLForecastRun.reading_type == reading_type,
        MLForecastRun.model == model,
        MLForecastRun.status == "completed",
    )
    if run_id is not None:
        query = query.filter(MLForecastRun.id == run_id)
    else:
        query = query.filter(MLForecastRun.horizon == horizon).order_by(MLForecastRun.created_at.desc())
    run = query.first()
    if not run:
        raise HTTPException(404, "no saved prediction found for this selection")

    try:
        forecast = [float(v) for v in json.loads(run.forecast_json or "[]") if v is not None]
    except (TypeError, ValueError):
        forecast = []
    if not forecast:
        raise HTTPException(404, "saved prediction has no forecast values")

    observed_rows = (
        db.query(models.SensorReading)
        .filter_by(machine_id=machine_id, reading_type=reading_type)
        .order_by(models.SensorReading.recorded_at.desc(), models.SensorReading.id.desc())
        .limit(32)
        .all()
    )
    observed = [float(r.value) for r in reversed(observed_rows)]

    from reportlab.graphics.shapes import Drawing, Line, PolyLine, String
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    values = observed + forecast
    vmin, vmax = min(values), max(values)
    vrange = vmax - vmin or 1.0
    width, height = 520, 240
    pad_x, pad_y = 35, 28
    chart = Drawing(width, height)
    chart.add(Line(pad_x, pad_y, width - 10, pad_y, strokeColor=colors.HexColor("#b8c0cc")))
    chart.add(Line(pad_x, pad_y, pad_x, height - 18, strokeColor=colors.HexColor("#b8c0cc")))

    def point(index, value):
        x = pad_x + (index / max(len(values) - 1, 1)) * (width - pad_x - 10)
        y = pad_y + ((value - vmin) / vrange) * (height - pad_y - 28)
        return x, y

    if len(observed) > 1:
        points = [coord for i, value in enumerate(observed) for coord in point(i, value)]
        chart.add(PolyLine(points, strokeColor=colors.HexColor("#4c8dff"), strokeWidth=2.2))
    forecast_points = []
    if observed:
        forecast_points.extend(point(len(observed) - 1, observed[-1]))
    for i, value in enumerate(forecast):
        forecast_points.extend(point(len(observed) + i, value))
    chart.add(PolyLine(forecast_points, strokeColor=colors.HexColor("#f0a23a"), strokeWidth=2.2, strokeDashArray=[6, 4]))
    chart.add(String(pad_x, height - 12, "Observed telemetry", fontSize=8, fillColor=colors.HexColor("#4c8dff")))
    chart.add(String(width - 105, height - 12, "Forecast", fontSize=8, fillColor=colors.HexColor("#f0a23a")))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=16 * mm, bottomMargin=16 * mm, leftMargin=16 * mm, rightMargin=16 * mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("PredictionTitle", parent=styles["Title"], textColor=colors.HexColor("#4c8dff"))
    h2 = ParagraphStyle("PredictionH2", parent=styles["Heading2"], spaceBefore=12, spaceAfter=6)
    story = [
        Paragraph("MAINTAIN AI", title),
        Paragraph("Saved Prediction Report", styles["Heading2"]),
        Paragraph(f"Generated {datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')}", styles["Normal"]),
        Spacer(1, 8),
    ]
    meta = [
        ["Machine", machine.name], ["Machine Code", machine.machine_code],
        ["Signal", reading_type], ["Model", run.model], ["Horizon", str(run.horizon)],
        ["Prediction Time", run.created_at.strftime("%d %b %Y, %H:%M UTC") if run.created_at else "—"],
        ["Input Samples", str(run.input_reading_count)], ["Trend", run.trend or "—"],
        ["Next Prediction", str(run.next_prediction if run.next_prediction is not None else "—")],
        ["End Prediction", str(run.end_prediction if run.end_prediction is not None else "—")],
    ]
    story.append(_table([["Field", "Value"]] + meta, [45 * mm, 115 * mm]))
    story.append(Paragraph("Observed vs Forecast", h2))
    story.append(chart)
    story.append(Paragraph("Forecast Values", h2))
    value_rows = [["Step", "Predicted Value"]]
    value_rows.extend([[f"t+{i + 1}", f"{value:.4f}"] for i, value in enumerate(forecast)])
    story.append(_table(value_rows, [45 * mm, 115 * mm]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Evidence note: observed values are recent telemetry stored by MAINTAIN AI; forecast values are the saved output of the selected model run. This report does not replace technician verification or safety procedures.", styles["Normal"]))
    doc.build(story)
    buffer.seek(0)
    filename = f"maintain_ai_prediction_{machine.machine_code}_{reading_type}_{run.id}.pdf"
    return StreamingResponse(iter([buffer.getvalue()]), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={filename}"})

@router.get("/export/{dataset}.csv")
def export_dataset_csv(dataset: str, db: Session = Depends(get_db), current: CurrentUser = Depends(get_current_user)):
    allowed = {"machines","workorders","maintenance","faults","alerts","sensor_readings","components","safety","safety_events","spare_parts","notifications"}
    if dataset not in allowed:
        from fastapi import HTTPException
        raise HTTPException(404, "unknown export dataset")
    headers, rows = _export_dataset(db, dataset, current)
    filename = f"maintain_ai_{dataset}_{datetime.utcnow().date()}.csv"
    return StreamingResponse(iter([_csv_bytes(headers, rows)]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/export/all")
def export_all_data(db: Session = Depends(get_db), current: CurrentUser = Depends(get_current_user)):
    allowed = ["machines","workorders","maintenance","faults","alerts","sensor_readings","components","safety","safety_events","spare_parts","notifications"]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        manifest = {"generated_at_utc": datetime.utcnow().isoformat() + "Z", "datasets": allowed}
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        for dataset in allowed:
            headers, rows = _export_dataset(db, dataset, current)
            archive.writestr(f"{dataset}.csv", _csv_bytes(headers, rows))
    buffer.seek(0)
    filename = f"maintain_ai_full_export_{datetime.utcnow().date()}.zip"
    return StreamingResponse(iter([buffer.getvalue()]), media_type="application/zip", headers={"Content-Disposition": f"attachment; filename={filename}"})


