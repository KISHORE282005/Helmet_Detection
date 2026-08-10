"""Aggregations for the analytics page."""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Query

from ..state import get_db

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

RANGE_DAYS = {"7d": 7, "30d": 30, "90d": 90}


def _range(range_key, date_from, date_to):
    if date_from and date_to:
        return date_from, date_to
    days = RANGE_DAYS.get(range_key, 7)
    end = date.today()
    return (end - timedelta(days=days - 1)).isoformat(), end.isoformat()


def _fill_days(rows, start, end):
    """Return one point per day so the trend has no invisible gaps."""
    counts = {r["key"]: r["count"] for r in rows}
    cursor = date.fromisoformat(start)
    last = date.fromisoformat(end)
    series = []
    while cursor <= last:
        key = cursor.isoformat()
        series.append({"date": key, "count": counts.get(key, 0)})
        cursor += timedelta(days=1)
    return series


@router.get("")
def analytics(
    range: str = Query("7d", pattern="^(7d|30d|90d|custom)$"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    db = get_db()
    start, end = _range(range, date_from, date_to)
    window = {"date_from": start, "date_to": end}

    totals = db.incident_totals(window)
    runs = db.analysis_totals(date_from=start, date_to=end)
    people = runs.get("people_detected") or 0
    incidents = totals.get("incidents") or 0

    return {
        "range": {"from": start, "to": end, "key": range},
        "totals": {
            "incidents": incidents,
            "raw_detections": runs.get("raw_detections", 0),
            "people_detected": people,
            "person_frames": runs.get("person_frames", 0),
            "frames_analyzed": runs.get("frames_analyzed", 0),
            "runs": runs.get("runs", 0),
            "avg_confidence": round(float(totals.get("avg_confidence") or 0.0), 4),
            "compliance_rate": (
                round(((people - min(incidents, people)) / people) * 100, 1)
                if people > 0 else None
            ),
            # How many duplicate detections the tracker collapsed away.
            "suppressed_duplicates": max(0, (runs.get("raw_detections") or 0) - incidents),
        },
        "trend": _fill_days(db.daily_counts(start, end), start, end),
        "by_camera": db.incidents_grouped("camera_id", window, limit=12),
        "by_location": db.incidents_grouped("location", window, limit=12),
        "by_status": db.incidents_grouped("status", window, limit=8),
        "by_hour": db.hourly_counts(start, end),
        "recent_runs": db.get_analysis_runs(limit=10),
    }
