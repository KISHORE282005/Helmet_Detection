"""The five-second view: camera health, open violations, today vs yesterday."""

from datetime import date, timedelta

from fastapi import APIRouter

from ..schemas import serialize_camera, serialize_incident
from ..state import get_camera_monitor, get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _delta(current, previous):
    """Percent change, or None when there is no baseline to compare against."""
    if previous == 0:
        return None
    return round(((current - previous) / previous) * 100, 1)


def _compliance(totals):
    """Share of tracked people who were never confirmed without a helmet.

    Returns None when nothing has been analyzed yet — an empty system has no
    compliance rate, and showing 100% would be a lie.
    """
    people = totals.get("people_detected") or 0
    if people <= 0:
        return None
    violators = min(totals.get("unique_incidents") or 0, people)
    return round(((people - violators) / people) * 100, 1)


@router.get("/summary")
def summary():
    db = get_db()
    monitor = get_camera_monitor()
    live = monitor.snapshot()

    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    week_start = (date.today() - timedelta(days=6)).isoformat()

    cameras = db.get_all_cameras(status=None)
    live_cameras = live.get("cameras", {})
    online = sum(1 for c in cameras
                 if live_cameras.get(c["camera_id"], {}).get("stream_status") == "online")
    offline = sum(1 for c in cameras
                  if live_cameras.get(c["camera_id"], {}).get("stream_status") == "offline")
    unconfigured = len(cameras) - online - offline

    today_count = db.count_incidents({"date_from": today, "date_to": today})
    yesterday_count = db.count_incidents({"date_from": yesterday, "date_to": yesterday})
    open_count = db.count_incidents({"status": "Open"})

    today_totals = db.analysis_totals(date_from=today, date_to=today)
    week_totals = db.analysis_totals(date_from=week_start, date_to=today)
    yesterday_totals = db.analysis_totals(date_from=yesterday, date_to=yesterday)

    compliance_today = _compliance(today_totals)
    compliance_yesterday = _compliance(yesterday_totals)
    compliance_delta = (
        round(compliance_today - compliance_yesterday, 1)
        if compliance_today is not None and compliance_yesterday is not None
        else None
    )

    recent = db.query_incidents({"status": "Open"}, limit=8)
    latest = db.query_incidents({}, limit=8)

    return {
        "generated_at": live.get("last_poll"),
        "cameras": {
            "total": len(cameras),
            "online": online,
            "offline": offline,
            "unconfigured": unconfigured,
            "last_poll": live.get("last_poll"),
        },
        "active_violations": {
            "count": open_count,
            "requires_attention": open_count > 0,
        },
        "today": {
            "violations": today_count,
            "previous": yesterday_count,
            "delta_percent": _delta(today_count, yesterday_count),
            "raw_detections": today_totals.get("raw_detections", 0),
            "people_detected": today_totals.get("people_detected", 0),
        },
        "compliance": {
            "rate": compliance_today,
            "delta": compliance_delta,
            "people_detected": today_totals.get("people_detected", 0),
            "basis": "confirmed violators vs tracked people, today",
        },
        "week": {
            "violations": db.count_incidents({"date_from": week_start, "date_to": today}),
            "people_detected": week_totals.get("people_detected", 0),
            "compliance": _compliance(week_totals),
            "trend": db.daily_counts(week_start, today),
        },
        "open_incidents": [serialize_incident(r) for r in recent],
        "latest_incidents": [serialize_incident(r) for r in latest],
        "camera_status": [
            serialize_camera(c, live_cameras.get(c["camera_id"])) for c in cameras
        ],
        "top_locations": db.incidents_grouped("location", {"date_from": week_start, "date_to": today}, limit=6),
    }
