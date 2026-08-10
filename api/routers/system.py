"""System health and the notification feed."""

from datetime import date, datetime

from fastapi import APIRouter

from ..schemas import serialize_incident
from ..services import analysis_manager
from ..state import get_camera_monitor, get_config, get_db, system_state

router = APIRouter(prefix="/api/system", tags=["system"])

STARTED_AT = datetime.now()


def _component(name, ok, detail, degraded=False):
    return {
        "name": name,
        "status": "degraded" if degraded else ("online" if ok else "offline"),
        "detail": detail,
    }


@router.get("/health")
def health():
    cfg = get_config()
    db = get_db()
    engine = system_state()
    monitor = get_camera_monitor()
    live = monitor.snapshot()
    cameras = live.get("cameras", {})
    online = sum(1 for c in cameras.values() if c.get("stream_status") == "online")
    configured = sum(1 for c in cameras.values() if c.get("stream_status") != "unconfigured")

    try:
        db.count()
        db_ok, db_detail = True, f"SQLite — {db.count()} incidents stored"
    except Exception as exc:
        db_ok, db_detail = False, str(exc)

    active = analysis_manager.active_job()
    helmet_weights = cfg.HELMET_MODEL_PATH.exists()

    components = [
        _component(
            "AI Engine",
            engine["error"] is None,
            "Models loaded" if engine["loaded"]
            else (engine["error"] or "Idle — loads on the first analysis"),
            degraded=not engine["loaded"] and engine["error"] is None,
        ),
        _component("Database", db_ok, db_detail),
        _component(
            "Camera Network",
            configured == 0 or online > 0,
            f"{online}/{configured} configured cameras reachable" if configured
            else "No camera IPs configured — Phase 1 runs on recorded video",
            degraded=configured > 0 and online < configured,
        ),
        _component(
            "RTSP Stream",
            online > 0,
            f"{online} live stream(s) reachable" if online
            else "Not connected — Phase 1 analyses recorded footage",
            degraded=online == 0 and configured > 0,
        ),
        _component(
            "YOLO Model",
            cfg.PERSON_MODEL_PATH.exists(),
            f"{cfg.PERSON_MODEL_PATH.name} present" if cfg.PERSON_MODEL_PATH.exists()
            else f"{cfg.PERSON_MODEL_PATH.name} missing from models/",
        ),
        _component(
            "Helmet Model",
            True,
            f"{cfg.HELMET_MODEL_PATH.name} present" if helmet_weights
            else "Using HSV crown-colour fallback (no helmet.pt)",
            degraded=not helmet_weights,
        ),
        _component("Tracker", True, "ByteTrack active"),
        _component(
            "Analysis Worker",
            True,
            f"Running: {active.upload['filename']}" if active else "Idle",
        ),
        _component(
            "Email Alerts",
            True,
            "Enabled" if cfg.EMAIL_ENABLED else "Disabled in configuration",
            degraded=not cfg.EMAIL_ENABLED,
        ),
    ]

    return {
        "phase": 1,
        "mode": "recorded" if online == 0 else "live",
        "server_time": datetime.now().isoformat(timespec="seconds"),
        "uptime_seconds": int((datetime.now() - STARTED_AT).total_seconds()),
        "components": components,
        "healthy": all(c["status"] == "online" for c in components),
        "camera_poll": {
            "last_poll": live.get("last_poll"),
            "interval_seconds": live.get("interval_seconds"),
        },
    }


@router.get("/notifications")
def notifications(limit: int = 20):
    """Recent unreviewed incidents, newest first — the supervisor work queue."""
    db = get_db()
    today = date.today().isoformat()
    rows = db.query_incidents({"status": "Open"}, limit=limit)
    return {
        "items": [
            {
                "id": incident["incident_id"],
                "kind": "violation",
                "title": incident["violation_type"],
                "camera_id": incident["camera_id"],
                "camera_name": incident["camera_name"],
                "location": incident["location"],
                "video_time": incident["video_time"],
                "detected_at": incident["detected_at"],
                "confidence": incident["confidence"],
                "evidence": incident["evidence"],
            }
            for incident in (serialize_incident(r) for r in rows)
        ],
        "unread": db.count_incidents({"status": "Open"}),
        "today": db.count_incidents({"date_from": today, "date_to": today}),
        "channels": [
            {"name": "In-app", "status": "active"},
            {"name": "Email", "status": "active" if get_config().EMAIL_ENABLED else "disabled"},
            {"name": "Microsoft Teams", "status": "planned"},
            {"name": "SMS", "status": "planned"},
        ],
    }
