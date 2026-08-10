"""Detection / tracking / incident configuration and AI model inventory.

Writes update the live `config` module so the next analysis picks them up.
They are process-scoped by design: nothing here rewrites config.py on disk.
"""

from fastapi import APIRouter

from ..schemas import SettingsPayload
from ..state import get_config, system_state

router = APIRouter(prefix="/api/settings", tags=["settings"])

FIELD_GROUPS = [
    {
        "id": "detection",
        "title": "Detection",
        "description": "How confident the models must be before a frame counts.",
        "fields": [
            {"key": "CONFIDENCE_THRESHOLD", "label": "Person confidence", "type": "ratio",
             "min": 0.1, "max": 0.95, "step": 0.05,
             "help": "Minimum YOLO score for a person box to be tracked."},
            {"key": "HELMET_CONFIDENCE_THRESHOLD", "label": "Helmet confidence", "type": "ratio",
             "min": 0.5, "max": 0.99, "step": 0.01,
             "help": "Below this, the frame is ignored rather than counted either way."},
            {"key": "HELMET_MIN_RATIO", "label": "Helmet crown coverage", "type": "ratio",
             "min": 0.1, "max": 0.9, "step": 0.05,
             "help": "Share of the crown region that must match a helmet colour."},
            {"key": "FRAME_SKIP", "label": "Frame skip", "type": "int", "min": 1, "max": 30,
             "help": "1 analyses every frame. Higher is faster but can miss short violations."},
            {"key": "RESIZE_WIDTH", "label": "Analysis width", "type": "int",
             "min": 640, "max": 1920, "step": 32,
             "help": "Frames are resized to this width before inference."},
        ],
    },
    {
        "id": "tracking",
        "title": "Tracking",
        "description": "How long a person keeps the same identity across frames.",
        "fields": [
            {"key": "MAX_TRACK_AGE", "label": "Maximum track age", "type": "int",
             "min": 5, "max": 300,
             "help": "Frames a track survives without a detection before it is dropped."},
            {"key": "CONSECUTIVE_GAP_RESET", "label": "Gap reset", "type": "int",
             "min": 0, "max": 120,
             "help": "Missing for longer than this resets the violation counter."},
        ],
    },
    {
        "id": "incidents",
        "title": "Incident management",
        "description": "The rules that turn repeated detections into one incident.",
        "fields": [
            {"key": "VIOLATION_REQUIRED_FRAMES", "label": "Confirmation frames", "type": "int",
             "min": 1, "max": 300,
             "help": "Consecutive no-helmet frames required before an incident is created."},
            {"key": "GROUP_CAPTURE_ENABLED", "label": "Group capture", "type": "bool",
             "help": "People confirmed together share one evidence image."},
            {"key": "GROUP_WINDOW_FRAMES", "label": "Group window", "type": "int",
             "min": 0, "max": 300,
             "help": "Frame window within which violations are treated as one scene."},
        ],
    },
    {
        "id": "notifications",
        "title": "Notifications",
        "description": "Supervisor alerting for confirmed incidents.",
        "fields": [
            {"key": "EMAIL_ENABLED", "label": "Email alerts", "type": "bool",
             "help": "Send the evidence image to the camera's mapped supervisor."},
        ],
    },
]


def _current(cfg):
    values = {}
    for group in FIELD_GROUPS:
        for field in group["fields"]:
            value = getattr(cfg, field["key"], None)
            values[field["key"]] = bool(value) if field["type"] == "bool" else value
    return values


@router.get("")
def get_settings():
    cfg = get_config()
    return {
        "groups": FIELD_GROUPS,
        "values": _current(cfg),
        "notes": {
            "one_incident_per_track": True,
            "scope": "Changes apply to the next analysis run in this process; "
                     "config.py on disk is not modified.",
        },
    }


@router.patch("")
def update_settings(payload: SettingsPayload):
    cfg = get_config()
    changes = {}
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            continue
        current = getattr(cfg, key, None)
        if current != value:
            setattr(cfg, key, value)
            changes[key] = {"from": current, "to": value}
    return {"values": _current(cfg), "changed": changes}


@router.get("/models")
def models():
    """Model inventory, including the Phase 2 recognition stack (not active)."""
    cfg = get_config()
    person_model = cfg.PERSON_MODEL_PATH
    helmet_model = cfg.HELMET_MODEL_PATH
    engine = system_state()

    return {
        "engine": {
            "loaded": engine["loaded"],
            "error": engine["error"],
            "detail": "Models load on the first analysis run.",
        },
        "models": [
            {
                "role": "Person detection",
                "name": person_model.name,
                "framework": "Ultralytics YOLO11",
                "status": "available" if person_model.exists() else "missing",
                "size_mb": round(person_model.stat().st_size / (1024 * 1024), 1)
                if person_model.exists() else None,
                "phase": 1,
            },
            {
                "role": "Helmet classification",
                "name": helmet_model.name,
                "framework": "YOLO weights, with an HSV colour fallback",
                "status": "available" if helmet_model.exists() else "fallback",
                "size_mb": round(helmet_model.stat().st_size / (1024 * 1024), 1)
                if helmet_model.exists() else None,
                "phase": 1,
                "note": None if helmet_model.exists()
                else "No helmet weights found — the pipeline is using crown colour analysis.",
            },
            {
                "role": "Multi-object tracking",
                "name": "ByteTrack",
                "framework": "boxmot",
                "status": "available",
                "size_mb": None,
                "phase": 1,
            },
            {
                "role": "Face detection",
                "name": "RetinaFace",
                "framework": "InsightFace",
                "status": "planned",
                "size_mb": None,
                "phase": 2,
            },
            {
                "role": "Face embedding",
                "name": "ArcFace",
                "framework": "InsightFace",
                "status": "planned",
                "size_mb": None,
                "phase": 2,
            },
        ],
        "employee_recognition": {
            "enabled": False,
            "status": "Planned for Phase 2",
            "components": ["RetinaFace — face detection", "ArcFace — face embedding"],
            "note": "Incidents are attributed to anonymous track IDs until this ships.",
        },
    }
