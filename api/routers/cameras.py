"""Camera master data, live connection state, and live stream analysis."""

import logging
from datetime import date

import cv2
from fastapi import APIRouter, HTTPException, Response

import config as cfg
from utils import grab_snapshot

from ..schemas import CameraAIToggle, CameraPayload, serialize_camera, serialize_supervisor
from ..services.camera_monitor import probe_camera
from ..services.live_stream import camera_stream_url, live_manager, verify_stream
from ..state import get_camera_monitor, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


def _require_camera(camera_id):
    camera = get_db().get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
    return camera


def _with_live(camera, live_state, violations_today):
    state = dict(live_state or {})
    state["violations_today"] = violations_today.get(camera["camera_id"], 0)
    return serialize_camera(camera, state)


def _violations_today(db):
    today = date.today().isoformat()
    rows = db.incidents_grouped("camera_id", {"date_from": today, "date_to": today}, limit=200)
    return {r["key"]: r["count"] for r in rows}


@router.get("")
def list_cameras():
    db = get_db()
    live = get_camera_monitor().snapshot()
    counts = _violations_today(db)
    cameras = db.get_all_cameras(status=None)
    return {
        "items": [
            _with_live(c, live.get("cameras", {}).get(c["camera_id"]), counts)
            for c in cameras
        ],
        "last_poll": live.get("last_poll"),
        "poll_interval_seconds": live.get("interval_seconds"),
        "supervisors": [serialize_supervisor(s) for s in db.get_all_supervisors(status=None)],
    }


# Declared before /{camera_id} so the literal path is matched first.
@router.get("/live/sessions")
def list_live_sessions():
    """Every live analysis session this process has run, newest state included."""
    sessions = live_manager.list()
    return {
        "items": [s.to_dict() for s in sessions],
        "active_camera_ids": live_manager.active_camera_ids(),
        "max_sessions": int(getattr(cfg, "LIVE_MAX_SESSIONS", 1)),
    }


@router.get("/{camera_id}")
def get_camera(camera_id: str):
    db = get_db()
    camera = _require_camera(camera_id)
    live = get_camera_monitor().state_for(camera_id)
    return _with_live(camera, live, _violations_today(db))


@router.post("", status_code=201)
def create_camera(payload: CameraPayload):
    db = get_db()
    if db.get_camera(payload.camera_id) is not None:
        raise HTTPException(status_code=409, detail=f"Camera {payload.camera_id} already exists")
    db.upsert_camera(payload.model_dump())
    return get_camera(payload.camera_id)


@router.put("/{camera_id}")
def update_camera(camera_id: str, payload: CameraPayload):
    db = get_db()
    existing = db.get_camera(camera_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
    data = payload.model_dump()
    data["camera_id"] = camera_id
    # Connection state belongs to the monitor, not to the edit form.
    data["stream_status"] = existing.get("stream_status", "unknown")
    data["last_seen"] = existing.get("last_seen", "")
    db.upsert_camera(data)
    return get_camera(camera_id)


@router.delete("/{camera_id}", status_code=204)
def delete_camera(camera_id: str):
    db = get_db()
    _require_camera(camera_id)
    # Otherwise the session keeps streaming and filing incidents against a
    # camera that no longer exists.
    live_manager.stop(camera_id)
    db.delete_camera(camera_id)


@router.post("/{camera_id}/test")
def test_connection(camera_id: str, deep: bool = False):
    """Check the camera. No credentials are returned by either mode.

    The default is a TCP connect to the RTSP port — fast, and all the existing
    dashboard button needs. `?deep=true` performs a real RTSP handshake and
    decodes a frame, which is what actually proves the login and channel are
    right.
    """
    db = get_db()
    camera = _require_camera(camera_id)

    status = probe_camera(camera.get("ip_address"), camera.get("rtsp_port"))
    messages = {
        "online": f"RTSP port {camera.get('rtsp_port') or 554} is accepting connections",
        "offline": "No response on the RTSP port — check the network path and camera power",
        "unconfigured": "No IP address configured for this camera",
    }
    message = messages[status]
    stream_ok = None

    if deep and status != "unconfigured":
        stream_ok, message = verify_stream(camera)
        # A port that answers but will not stream is not a usable camera, so
        # the recorded state follows the stricter result.
        status = "online" if stream_ok else "offline"

    db.update_camera_stream(camera_id, status)
    return {
        "camera_id": camera_id,
        "stream_status": status,
        "stream_verified": stream_ok,
        "message": message,
        "checked_at": get_camera_monitor().state_for(camera_id).get("checked_at"),
    }


@router.get("/{camera_id}/snapshot")
def camera_snapshot(camera_id: str):
    """One JPEG frame pulled straight from the camera's RTSP stream."""
    camera = _require_camera(camera_id)
    url = camera_stream_url(camera)
    if not url:
        raise HTTPException(
            status_code=409, detail=f"Camera {camera_id} has no IP address configured"
        )

    frame = grab_snapshot(url, cfg)
    if frame is None:
        raise HTTPException(
            status_code=502,
            detail=(
                f"No video from {camera.get('ip_address')}. Check that the camera is "
                f"reachable and that RTSP_USERNAME / RTSP_PASSWORD in .env are correct."
            ),
        )

    ok, buffer = cv2.imencode(".jpg", frame)
    if not ok:
        raise HTTPException(status_code=500, detail="Could not encode the captured frame")
    return Response(
        content=buffer.tobytes(),
        media_type="image/jpeg",
        # A snapshot is only meaningful at the moment it was taken.
        headers={"Cache-Control": "no-store"},
    )


@router.get("/{camera_id}/live")
def live_status(camera_id: str):
    _require_camera(camera_id)
    session = live_manager.get(camera_id)
    if session is None:
        return {"camera_id": camera_id, "status": "idle", "session": None}
    return {"camera_id": camera_id, "status": session.status, "session": session.to_dict()}


@router.post("/{camera_id}/live/start", status_code=202)
def start_live(camera_id: str):
    """Connect to the camera and run helmet detection on the live feed."""
    camera = _require_camera(camera_id)
    try:
        session = live_manager.start(camera)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return session.to_dict()


@router.post("/{camera_id}/live/stop")
def stop_live(camera_id: str):
    _require_camera(camera_id)
    session = live_manager.stop(camera_id)
    if session is None:
        raise HTTPException(
            status_code=404, detail=f"No live session for camera {camera_id}"
        )
    return session.to_dict()


@router.post("/{camera_id}/ai")
def toggle_ai(camera_id: str, payload: CameraAIToggle):
    db = get_db()
    if db.get_camera(camera_id) is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
    db.set_camera_ai(camera_id, payload.enabled)
    return get_camera(camera_id)


@router.post("/refresh")
def refresh_all():
    """Re-probe every camera immediately instead of waiting for the poll."""
    monitor = get_camera_monitor()
    monitor.poll_once()
    return list_cameras()
