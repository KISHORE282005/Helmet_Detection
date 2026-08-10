"""Daily / weekly / monthly safety reports and their exports."""

import io
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..state import get_db

router = APIRouter(prefix="/api/reports", tags=["reports"])

PERIODS = ("daily", "weekly", "monthly")

EXPORT_COLUMNS = [
    ("incident_id", "Incident ID"),
    ("date", "Date"),
    ("timestamp", "Video Time"),
    ("detected_at", "Recorded At"),
    ("camera_id", "Camera ID"),
    ("camera_name", "Camera Name"),
    ("location", "Location"),
    ("violation_type", "Violation"),
    ("confidence", "Confidence"),
    ("track_id", "Track ID"),
    ("status", "Status"),
    ("scene_persons", "Persons In Frame"),
    ("scene_helmet", "With Helmet"),
    ("scene_no_helmet", "Without Helmet"),
    ("video_name", "Source"),
    ("reviewed_by", "Reviewed By"),
    ("remarks", "Remarks"),
]


def _period_bounds(period, anchor=None):
    today = date.fromisoformat(anchor) if anchor else date.today()
    if period == "daily":
        return today, today
    if period == "weekly":
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    if period == "monthly":
        start = today.replace(day=1)
        next_month = (start + timedelta(days=32)).replace(day=1)
        return start, next_month - timedelta(days=1)
    raise HTTPException(status_code=422, detail=f"period must be one of {', '.join(PERIODS)}")


def _compliance(runs):
    people = runs.get("people_detected") or 0
    if people <= 0:
        return None
    violators = min(runs.get("unique_incidents") or 0, people)
    return round(((people - violators) / people) * 100, 1)


def _build(period, anchor=None):
    db = get_db()
    start, end = _period_bounds(period, anchor)
    window = {"date_from": start.isoformat(), "date_to": end.isoformat()}

    totals = db.incident_totals(window)
    runs = db.analysis_totals(date_from=start.isoformat(), date_to=end.isoformat())
    by_camera = db.incidents_grouped("camera_id", window, limit=20)
    by_location = db.incidents_grouped("location", window, limit=20)
    by_status = db.incidents_grouped("status", window, limit=8)

    return {
        "period": period,
        "range": {"from": start.isoformat(), "to": end.isoformat()},
        "label": {
            "daily": start.strftime("%d %b %Y"),
            "weekly": f"{start.strftime('%d %b')} - {end.strftime('%d %b %Y')}",
            "monthly": start.strftime("%B %Y"),
        }[period],
        "totals": {
            "violations": totals.get("incidents", 0),
            "raw_detections": runs.get("raw_detections", 0),
            "people_detected": runs.get("people_detected", 0),
            "analysis_runs": runs.get("runs", 0),
            "compliance_rate": _compliance(runs),
            "avg_confidence": round(float(totals.get("avg_confidence") or 0.0), 4),
        },
        "worst_camera": by_camera[0] if by_camera else None,
        "worst_location": by_location[0] if by_location else None,
        "by_camera": by_camera,
        "by_location": by_location,
        "by_status": by_status,
        "trend": db.daily_counts(start.isoformat(), end.isoformat()),
        "has_data": (totals.get("incidents", 0) or 0) > 0 or (runs.get("runs", 0) or 0) > 0,
    }


@router.get("/summary")
def all_periods(anchor: Optional[str] = None):
    return {"reports": [_build(p, anchor) for p in PERIODS]}


@router.get("/{period}")
def report(period: str, anchor: Optional[str] = None):
    if period not in PERIODS:
        raise HTTPException(status_code=422, detail=f"period must be one of {', '.join(PERIODS)}")
    data = _build(period, anchor)
    db = get_db()
    data["incidents"] = db.query_incidents(
        {"date_from": data["range"]["from"], "date_to": data["range"]["to"]}, limit=500
    )
    from ..schemas import serialize_incident

    data["incidents"] = [serialize_incident(r) for r in data["incidents"]]
    return data


def _export_frame(period, anchor):
    db = get_db()
    data = _build(period, anchor)
    rows = db.query_incidents(
        {"date_from": data["range"]["from"], "date_to": data["range"]["to"]}, limit=5000
    )
    frame = pd.DataFrame(rows, columns=[c[0] for c in EXPORT_COLUMNS]) if rows else pd.DataFrame(
        columns=[c[0] for c in EXPORT_COLUMNS]
    )
    frame.columns = [c[1] for c in EXPORT_COLUMNS]
    return data, frame


@router.get("/{period}/export")
def export_report(period: str, format: str = Query("xlsx", pattern="^(xlsx|csv|pdf)$"),
                  anchor: Optional[str] = None):
    if period not in PERIODS:
        raise HTTPException(status_code=422, detail=f"period must be one of {', '.join(PERIODS)}")
    data, frame = _export_frame(period, anchor)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"SafeVision_{period.capitalize()}_Report_{stamp}"

    if format == "csv":
        buffer = io.StringIO()
        frame.to_csv(buffer, index=False)
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{base}.csv"'},
        )

    if format == "xlsx":
        return StreamingResponse(
            iter([_to_xlsx(data, frame)]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{base}.xlsx"'},
        )

    return StreamingResponse(
        iter([_to_pdf(data, frame)]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{base}.pdf"'},
    )


def _to_xlsx(data, frame):
    summary = pd.DataFrame(
        [
            ("Report period", data["label"]),
            ("Range", f"{data['range']['from']} to {data['range']['to']}"),
            ("Unique incidents", data["totals"]["violations"]),
            ("Raw helmet-missing detections", data["totals"]["raw_detections"]),
            ("People tracked", data["totals"]["people_detected"]),
            ("Compliance rate (%)", data["totals"]["compliance_rate"]),
            ("Average confidence", data["totals"]["avg_confidence"]),
            ("Analysis runs", data["totals"]["analysis_runs"]),
            ("Most affected camera", (data["worst_camera"] or {}).get("key", "n/a")),
            ("Most affected location", (data["worst_location"] or {}).get("key", "n/a")),
            ("Generated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ],
        columns=["Metric", "Value"],
    )

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        frame.to_excel(writer, sheet_name="Incidents", index=False)
        pd.DataFrame(data["by_camera"]).to_excel(writer, sheet_name="By Camera", index=False)
        pd.DataFrame(data["by_location"]).to_excel(writer, sheet_name="By Location", index=False)
        for name, sheet in writer.sheets.items():
            for column in sheet.columns:
                width = max(len(str(cell.value or "")) for cell in column) + 2
                sheet.column_dimensions[column[0].column_letter].width = min(width, 48)
    return buffer.getvalue()


def _to_pdf(data, frame):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
        title=f"SafeVision AI {data['period'].capitalize()} Report",
    )
    styles = getSampleStyleSheet()
    ink = colors.HexColor("#0f172a")
    accent = colors.HexColor("#0ea5e9")

    story = [
        Paragraph("<b>SafeVision AI</b> — Industrial PPE Safety Report", styles["Title"]),
        Paragraph(
            f"{data['period'].capitalize()} report &nbsp;|&nbsp; {data['label']} "
            f"&nbsp;|&nbsp; generated {datetime.now().strftime('%d %b %Y %H:%M')}",
            styles["Normal"],
        ),
        Spacer(1, 8 * mm),
    ]

    metrics = [
        ["Unique incidents", data["totals"]["violations"]],
        ["Raw helmet-missing detections", data["totals"]["raw_detections"]],
        ["People tracked", data["totals"]["people_detected"]],
        ["Compliance rate", f"{data['totals']['compliance_rate']}%"
            if data["totals"]["compliance_rate"] is not None else "no data"],
        ["Average confidence", f"{data['totals']['avg_confidence'] * 100:.1f}%"],
        ["Most affected camera", (data["worst_camera"] or {}).get("key", "n/a")],
        ["Most affected location", (data["worst_location"] or {}).get("key", "n/a")],
    ]
    summary_table = Table(metrics, colWidths=[70 * mm, 60 * mm])
    summary_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
        ("TEXTCOLOR", (0, 0), (-1, -1), ink),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [summary_table, Spacer(1, 8 * mm),
              Paragraph("<b>Incidents</b>", styles["Heading3"])]

    columns = ["Incident ID", "Date", "Video Time", "Camera ID", "Location",
               "Violation", "Confidence", "Status"]
    if frame.empty:
        story.append(Paragraph("No incidents recorded in this period.", styles["Normal"]))
    else:
        subset = frame[columns].head(300).copy()
        subset["Confidence"] = subset["Confidence"].map(
            lambda v: f"{float(v) * 100:.0f}%" if pd.notna(v) else ""
        )
        table = Table([columns] + subset.values.tolist(), repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), accent),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("PADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(table)
        if len(frame) > 300:
            story += [Spacer(1, 4 * mm), Paragraph(
                f"Showing the first 300 of {len(frame)} incidents. "
                "Export to Excel for the complete set.", styles["Italic"])]

    doc.build(story)
    return buffer.getvalue()
