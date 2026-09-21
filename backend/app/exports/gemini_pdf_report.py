"""Detailed Gemini-assisted PDF report for MAINTAIN AI."""
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from sqlalchemy.orm import Session
from .. import models

def _val(v): return getattr(v, "value", v)

def _table(data, widths):
    t=Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1f2733")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),7.5),
        ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#cccccc")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f5f6f8")]),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
    ]))
    return t

def _p(text, style):
    return Paragraph(str(text).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\n","<br/>"), style)

def build_gemini_pdf_report(db: Session, facts: list, ai: dict | None) -> bytes:
    buf=io.BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=A4,topMargin=15*mm,bottomMargin=15*mm,leftMargin=14*mm,rightMargin=14*mm)
    styles=getSampleStyleSheet()
    title=ParagraphStyle("GT",parent=styles["Title"],textColor=colors.HexColor("#4c8dff"))
    h2=ParagraphStyle("GH",parent=styles["Heading2"],spaceBefore=12,spaceAfter=6)
    body=ParagraphStyle("GB",parent=styles["BodyText"],fontSize=9,leading=13)
    small=ParagraphStyle("GS",parent=body,fontSize=7.5,leading=10)
    story=[Paragraph("MAINTAIN AI",title),Paragraph("AI-Assisted Maintenance Intelligence Report",styles["Heading2"]),Paragraph(f"Generated {datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')}",small),Spacer(1,8)]
    story.append(Paragraph("AI Executive Assessment",h2))
    if ai:
        story.append(_p(ai.get("safety_notice","Safety note: follow site isolation and emergency procedures."),body))
        causes=ai.get("possible_causes") or []
        if causes:
            story.append(Spacer(1,5)); story.append(_table([["Possible Cause","Confidence","Certainty"]]+[[x.get("cause",""),x.get("confidence",""),x.get("certainty","")] for x in causes], [85*mm,30*mm,45*mm]))
        if ai.get("recommended_procedure"):
            story.append(Spacer(1,5)); story.append(Paragraph("Recommended Procedure",h2))
            for i,step in enumerate(ai["recommended_procedure"],1): story.append(_p(f"{i}. {step}",body)); story.append(Spacer(1,2))
        if ai.get("needs_more_info"):
            story.append(_p("Gemini identified additional information needed for diagnosis; this report does not treat an unconfirmed cause as confirmed.",small))
    else:
        story.append(_p("Gemini analysis was unavailable. The report below contains the collected MAINTAIN AI evidence without an AI-generated diagnosis.",body))

    for f in facts:
        m=f["machine"]; story.append(PageBreak()); story.append(Paragraph(f'{m["name"]} ({m["code"]})',h2))
        story.append(_table([["Category","Location","Department","Health","Status","Criticality","Operating Hours"],[m["category"],m["location"],m["department"],m["health_score"],m["status"],m["criticality"],m["operating_hours"]]], [28*mm,28*mm,28*mm,18*mm,22*mm,25*mm,30*mm]))
        for title_txt,key,headers,rows in [
            ("Fault History","faults",["ID","Description","Cause","Severity","Reported"],[[x["id"],x["description"],x["cause"],x["severity"],x["reported_date"]] for x in f["faults"]]),
            ("Work Orders","work_orders",["ID","Problem","Priority","Status","Assigned","Created","Completed","Resolution"],[[x["id"],x["problem"],x["priority"],x["status"],x["assigned_to"],x["created_at"],x["completed_at"],x["resolution_notes"]] for x in f["work_orders"]]),
            ("Maintenance History","maintenance",["ID","Type","Description","Status","Scheduled","Completed","Performed By","Notes"],[[x["id"],x["type"],x["description"],x["status"],x["scheduled_date"],x["completed_date"],x["performed_by"],x["notes"]] for x in f["maintenance"]]),
            ("Alerts","alerts",["Type","Severity","Message","Created","Acknowledged","Resolved"],[[x["type"],x["severity"],x["message"],x["created_at"],x["acknowledged"],x["resolved"]] for x in f["alerts"]]),
        ]:
            if rows:
                story.append(Paragraph(title_txt,h2))
                story.append(_table([headers]+rows,[max(16*mm,145*mm/len(headers))]*len(headers)))
        if f["recent_readings"]:
            story.append(Paragraph("Recent Telemetry Evidence",h2))
            story.append(_table([["Signal","Value","Unit","Recorded"]]+[[x["type"],x["value"],x["unit"],x["recorded_at"]] for x in f["recent_readings"]], [35*mm,25*mm,25*mm,70*mm]))
    story.append(PageBreak()); story.append(Paragraph("Report Scope & Evidence",h2))
    story.append(_p("This report combines machine records, faults, work orders, maintenance history, alerts and recent telemetry available in MAINTAIN AI at generation time. Gemini narrative is advisory and is constrained to the supplied evidence; it does not replace site safety procedures or technician verification.",body))
    doc.build(story); buf.seek(0); return buf.getvalue()
