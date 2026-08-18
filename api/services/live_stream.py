"""Live RTSP analysis sessions.

A recorded analysis has a definite end, so those run through a single worker
queue. A live session does not end on its own, so it gets its own thread: put
it on the recorded queue and one camera would block every uploaded video for as
long as it stayed connected.

Nothing here ever returns or logs a full RTSP URL — that string carries the
camera password. `config.redact_rtsp_url` is the only form allowed out.
"""

import logging
import threading
import uuid
from datetime import datetime

import config as cfg
from utils import probe_stream

from ..state import get_db, new_system

logger = logging.getLogger(__name__)


def camera_stream_url(camera):
    """Server-side RTSP URL for a camera row, or None when no IP is set."""
    return cfg.rtsp_url_for_camera(camera)


def verify_stream(camera, warmup_frames=3):
    """Actually connect to the camera and decode a frame.

    This is the honest version of the reachability check: the TCP probe in
    camera_monitor only proves something is listening on port 554, while this
    proves the credentials work and video is flowing. It costs a full RTSP
    handshake, so it is used on demand rather than on the poll loop.
    """
    url = camera_stream_url(camera)
    if not url:
        return False, "No IP address configured for this camera"
    try:
        frame, reason = probe_stream(url, cfg, warmup_frames=warmup_frames)
    except Exception as exc:
        logger.warning(f"Stream verification error for {camera.get('camera_id')}: {exc}")
        return False, cfg.redact_rtsp_url(f"Stream error: {exc}")

    if reason == "connect_failed":
        return False, (
            f"Could not open an RTSP session with {camera.get('ip_address')}. Check the "
            f"address and port, that RTSP is enabled on the camera, and that nothing "
            f"between the server and the camera is blocking port "
            f"{camera.get('rtsp_port') or 554}."
        )
    if reason == "no_frames":
        return False, (
            "Connected to the camera but no video was returned. Check RTSP_USERNAME / "
            "RTSP_PASSWORD in .env and the stream channel "
            f"({camera.get('rtsp_channel') or cfg.RTSP_DEFAULT_CHANNEL})."
        )
    height, width = frame.shape[:2]
    return True, f"Live video confirmed at {width}x{height}"


class LiveSession:
    """One camera being analysed live: connecting -> running -> stopped."""

    def __init__(self, session_id, camera):
        self.session_id = session_id
        self.camera = camera
        self.camera_id = camera["camera_id"]
        self.status = "connecting"
        self.error = None
        self.started_at = datetime.now()
        self.finished_at = None
        self.stop_event = threading.Event()
        self.thread = None
        self.progress = {
            "frames_total": 0,
            "frames_read": 0,
            "frames_analyzed": 0,
            "progress": 0.0,
            "people_detected": 0,
            "person_frames": 0,
            "raw_detections": 0,
            "compliant_frames": 0,
            "incidents": 0,
            "processing_fps": 0.0,
            "elapsed_seconds": 0.0,
        }
        self.result = None

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "camera_id": self.camera_id,
            "camera_name": self.camera.get("camera_name") or "",
            "location": self.camera.get("location") or self.camera.get("area") or "",
            # Address only — never the URL, which would carry the password.
            "ip_address": self.camera.get("ip_address") or "",
            "rtsp_port": self.camera.get("rtsp_port") or 554,
            "rtsp_channel": self.camera.get("rtsp_channel") or "",
            "status": self.status,
            "error": self.error,
            "started_at": self.started_at.isoformat(timespec="seconds"),
            "finished_at": self.finished_at.isoformat(timespec="seconds") if self.finished_at else None,
            "progress": dict(self.progress),
            "result": self.result,
        }


class LiveSessionManager:
    def __init__(self):
        self._sessions = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self, camera):
        """Begin analysing a camera's live stream. Raises ValueError on refusal."""
        camera_id = camera["camera_id"]
        if not (camera.get("ip_address") or "").strip():
            raise ValueError(f"Camera {camera_id} has no IP address configured")

        max_sessions = int(getattr(cfg, "LIVE_MAX_SESSIONS", 1))
        with self._lock:
            if self._is_active(self._sessions.get(camera_id)):
                raise ValueError(f"Camera {camera_id} is already being analysed")
            running = sum(1 for s in self._sessions.values() if self._is_active(s))
            if running >= max_sessions:
                raise ValueError(
                    f"{running} live session(s) already running and LIVE_MAX_SESSIONS "
                    f"is {max_sessions}. Stop one before starting another."
                )
            session = LiveSession(uuid.uuid4().hex[:12], camera)
            self._sessions[camera_id] = session

        session.thread = threading.Thread(
            target=self._run, args=(session,), name=f"live-{camera_id}", daemon=True
        )
        session.thread.start()
        logger.info(f"Live analysis starting for {camera_id} (session {session.session_id})")
        return session

    def stop(self, camera_id):
        session = self.get(camera_id)
        if session is None:
            return None
        if self._is_active(session):
            session.stop_event.set()
            session.status = "stopping"
            logger.info(f"Live analysis stop requested for {camera_id}")
        return session

    def stop_all(self):
        for session in self.list():
            if self._is_active(session):
                session.stop_event.set()

    def get(self, camera_id):
        with self._lock:
            return self._sessions.get(camera_id)

    def list(self):
        with self._lock:
            return list(self._sessions.values())

    def active_camera_ids(self):
        with self._lock:
            return [cid for cid, s in self._sessions.items() if self._is_active(s)]

    @staticmethod
    def _is_active(session):
        return session is not None and session.status in ("connecting", "running", "stopping")

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------
    def _run(self, session):
        camera = session.camera
        url = camera_stream_url(camera)
        safe_url = cfg.redact_rtsp_url(url)
        db = get_db()

        try:
            system = new_system()
        except Exception as exc:
            session.status = "failed"
            session.error = f"Detection models failed to load: {exc}"
            session.finished_at = datetime.now()
            logger.exception(f"Live session {session.session_id} could not load models")
            return

        session.status = "running"
        logger.info(f"Live analysis connected: {camera['camera_id']} -> {safe_url}")

        try:
            result = system.process_video(
                url,
                camera_name=camera.get("camera_name"),
                camera_id=camera.get("camera_id"),
                location=camera.get("location") or camera.get("area"),
                progress_callback=session.progress.update,
                analysis_id=session.session_id,
                should_stop=session.stop_event.is_set,
                display_name=camera.get("camera_name") or camera["camera_id"],
            )
        except Exception as exc:
            session.status = "failed"
            # OpenCV quotes the URL it was handed back into its error text, so
            # this is scrubbed unconditionally rather than only when it looks
            # like it needs it.
            session.error = cfg.redact_rtsp_url(str(exc))
            session.finished_at = datetime.now()
            db.update_camera_stream(session.camera_id, "offline")
            logger.error(f"Live session {session.session_id} failed: {session.error}")
            return

        session.finished_at = datetime.now()
        session.status = "stopped"
        session.result = {
            "video_name": result.get("video_name"),
            "frames_analyzed": result.get("frames_processed", 0),
            "video_fps": result.get("video_fps", 0.0),
            "people_detected": result.get("people_detected", 0),
            "person_frames": result.get("person_frames", 0),
            "compliant_frames": result.get("compliant_frames", 0),
            "raw_detections": result.get("raw_detections", 0),
            "unique_incidents": result.get("violations", 0),
            "elapsed_seconds": round(result.get("elapsed_seconds", 0.0), 1),
            "processing_fps": round(result.get("processing_fps", 0.0), 1),
            "incident_ids": [i["incident_id"] for i in result.get("incidents", [])],
            "report_available": bool(result.get("report_path")),
            "nva": result.get("nva"),
            "nva_run_id": result.get("nva_run_id"),
        }
        self._persist_run(session, result)
        logger.info(
            f"Live session {session.session_id} stopped: "
            f"{session.result['unique_incidents']} incidents over "
            f"{session.result['elapsed_seconds']}s"
        )

    @staticmethod
    def _persist_run(session, result):
        """Record the session so live incidents count toward compliance rates."""
        nva = result.get("nva") or {}
        try:
            get_db().save_analysis_run({
                "run_id": session.session_id,
                "video_name": result.get("video_name", ""),
                # Distinguishes live coverage from uploaded footage in reports.
                "source_type": "rtsp",
                "camera_id": session.camera_id,
                "camera_name": session.camera.get("camera_name", ""),
                "location": session.camera.get("location") or session.camera.get("area", ""),
                "started_at": session.started_at.isoformat(timespec="seconds"),
                "finished_at": session.finished_at.isoformat(timespec="seconds"),
                "date": session.finished_at.strftime("%Y-%m-%d"),
                "total_frames": result.get("total_frames", 0),
                "frames_analyzed": result.get("frames_processed", 0),
                "people_detected": result.get("people_detected", 0),
                "person_frames": result.get("person_frames", 0),
                "compliant_frames": result.get("compliant_frames", 0),
                "raw_detections": result.get("raw_detections", 0),
                "unique_incidents": result.get("violations", 0),
                "elapsed_seconds": round(result.get("elapsed_seconds", 0.0), 1),
                "processing_fps": round(result.get("processing_fps", 0.0), 1),
                "status": "stopped",
                "observed_seconds": nva.get("observed_seconds", 0.0),
                "classified_seconds": nva.get("classified_seconds", 0.0),
                "va_seconds": nva.get("va_seconds", 0.0),
                "nnva_seconds": nva.get("nnva_seconds", 0.0),
                "nva_seconds": nva.get("nva_seconds", 0.0),
            })
        except Exception:
            logger.exception(f"Could not persist live run {session.session_id}")


live_manager = LiveSessionManager()
