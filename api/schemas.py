"""Request bodies and row -> API serializers.

Serializers exist so the wire format is defined in exactly one place: routers
never hand a raw sqlite row to the client, and secrets (RTSP credentials,
absolute filesystem paths) are stripped here rather than in each route.
"""

from typing import Optional

from pydantic import BaseModel, Field

from .state import media_ref


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------
class IncidentReview(BaseModel):
    status: str = Field(..., description="Confirmed | False Positive | Open | Resolved")
    reviewed_by: str = ""
    remarks: Optional[str] = None


class CameraPayload(BaseModel):
    camera_id: str
    camera_name: str
    department: str = ""
    area: str = ""
    location: str = ""
    ip_address: str = ""
    rtsp_port: int = 554
    rtsp_channel: str = ""
    supervisor_id: str = ""
    status: str = "Active"
    ai_enabled: bool = True
    target_fps: int = 0


class CameraAIToggle(BaseModel):
    enabled: bool


class AnalysisStart(BaseModel):
    upload_id: str
    camera_id: Optional[str] = None
    camera_name: Optional[str] = None
    location: Optional[str] = None


class SettingsPayload(BaseModel):
    """Runtime-tunable detection settings. Keys absent from the body are left
    untouched, so the UI can PATCH a single slider."""

    CONFIDENCE_THRESHOLD: Optional[float] = Field(None, ge=0.0, le=1.0)
    HELMET_CONFIDENCE_THRESHOLD: Optional[float] = Field(None, ge=0.0, le=1.0)
    FRAME_SKIP: Optional[int] = Field(None, ge=1, le=30)
    RESIZE_WIDTH: Optional[int] = Field(None, ge=320, le=3840)
    MAX_TRACK_AGE: Optional[int] = Field(None, ge=1, le=600)
    VIOLATION_REQUIRED_FRAMES: Optional[int] = Field(None, ge=1, le=300)
    CONSECUTIVE_GAP_RESET: Optional[int] = Field(None, ge=0, le=120)
    GROUP_WINDOW_FRAMES: Optional[int] = Field(None, ge=0, le=300)
    GROUP_CAPTURE_ENABLED: Optional[bool] = None
    EMAIL_ENABLED: Optional[bool] = None
    HELMET_MIN_RATIO: Optional[float] = Field(None, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------
def serialize_incident(row):
    """One confirmed violation. `video_time` is the offset inside the source
    clip; `detected_at` is when the pipeline wrote the record."""
    return {
        "incident_id": row.get("incident_id"),
        "camera_id": row.get("camera_id") or "",
        "camera_name": row.get("camera_name") or "",
        "location": row.get("location") or "",
        "video_name": row.get("video_name") or "",
        "video_time": row.get("timestamp") or "",
        "date": row.get("date") or "",
        "detected_at": row.get("detected_at") or "",
        "violation_type": row.get("violation_type") or "Helmet Missing",
        "confidence": round(float(row.get("confidence") or 0.0), 4),
        "track_id": row.get("track_id") or 0,
        "status": row.get("status") or "Open",
        "scene_persons": row.get("scene_persons") or 0,
        "scene_helmet": row.get("scene_helmet") or 0,
        "scene_no_helmet": row.get("scene_no_helmet") or 0,
        "confirm_frames": row.get("confirm_frames") or 0,
        "analysis_id": row.get("analysis_id") or "",
        "reviewed_at": row.get("reviewed_at") or "",
        "reviewed_by": row.get("reviewed_by") or "",
        "remarks": row.get("remarks") or "",
        # Filenames only — the client fetches them through /api/media.
        "evidence": media_ref("evidence", row.get("image_path")),
        "poster": media_ref("poster", row.get("poster_path")),
    }


def serialize_camera(row, live=None):
    """Camera master row plus live stream state.

    Deliberately omits every credential: the client sees an IP and a
    connection state, never a full RTSP URL.
    """
    live = live or {}
    return {
        "camera_id": row.get("camera_id"),
        "camera_name": row.get("camera_name") or "",
        "department": row.get("department") or "",
        "area": row.get("area") or "",
        "location": row.get("location") or row.get("area") or "",
        "ip_address": row.get("ip_address") or "",
        "rtsp_port": row.get("rtsp_port") or 554,
        "rtsp_channel": row.get("rtsp_channel") or "",
        "supervisor_id": row.get("supervisor_id") or "",
        "status": row.get("status") or "Active",
        "stream_status": live.get("stream_status") or row.get("stream_status") or "unknown",
        "ai_enabled": bool(row.get("ai_enabled", 1)),
        "target_fps": row.get("target_fps") or 0,
        "last_seen": live.get("last_seen") or row.get("last_seen") or "",
        "source": live.get("source", "none"),
        "fps": live.get("fps", 0.0),
        "violations_today": live.get("violations_today", 0),
    }


def serialize_supervisor(row):
    return {
        "supervisor_id": row.get("supervisor_id"),
        "supervisor_name": row.get("supervisor_name") or "",
        "department": row.get("department") or "",
        "email": row.get("email") or "",
        "status": row.get("status") or "Active",
    }
