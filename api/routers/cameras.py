"""Camera master data and live connection state."""

from datetime import date

from fastapi import APIRouter, HTTPException

from ..schemas import CameraAIToggle, CameraPayload, serialize_camera, serialize_supervisor
from ..services.camera_monitor import probe_camera
from ..state import get_camera_monitor, get_db

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


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


@router.get("/{camera_id}")
def get_camera(camera_id: str):
    db = get_db()
    camera = db.get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
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
    if db.get_camera(camera_id) is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
    db.delete_camera(camera_id)


@router.post("/{camera_id}/test")
def test_connection(camera_id: str):
    """TCP-connect to the camera's RTSP port. No credentials are used or shown."""
    db = get_db()
    camera = db.get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    status = probe_camera(camera.get("ip_address"), camera.get("rtsp_port"))
    db.update_camera_stream(camera_id, status)
    messages = {
        "online": f"RTSP port {camera.get('rtsp_port') or 554} is accepting connections",
        "offline": "No response on the RTSP port — check the network path and camera power",
        "unconfigured": "No IP address configured for this camera",
    }
    return {
        "camera_id": camera_id,
        "stream_status": status,
        "message": messages[status],
        "checked_at": get_camera_monitor().state_for(camera_id).get("checked_at"),
    }


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
