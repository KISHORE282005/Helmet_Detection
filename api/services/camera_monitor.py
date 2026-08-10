"""Camera reachability polling.

Phase 1 has no live RTSP ingest, so "online" here means exactly one thing:
the camera's RTSP port accepted a TCP connection within the timeout. That is
a real signal the operator can act on, and it is labelled as such in the UI
rather than being presented as a decoded video stream.
"""

import logging
import socket
import threading
import time
from datetime import datetime

import config as cfg

logger = logging.getLogger(__name__)

# Tunable from .env — see CAMERA_POLL_INTERVAL / CAMERA_CONNECT_TIMEOUT.
CONNECT_TIMEOUT = float(getattr(cfg, "CAMERA_CONNECT_TIMEOUT", 1.5))
POLL_INTERVAL = float(getattr(cfg, "CAMERA_POLL_INTERVAL", 20.0))
DEFAULT_RTSP_PORT = int(getattr(cfg, "RTSP_DEFAULT_PORT", 554))


def probe_camera(ip_address, port=None, timeout=None):
    """Return 'online', 'offline', or 'unconfigured'."""
    if not ip_address:
        return "unconfigured"
    try:
        target = (ip_address, int(port or DEFAULT_RTSP_PORT))
        with socket.create_connection(target, timeout=timeout or CONNECT_TIMEOUT):
            return "online"
    except OSError:
        return "offline"


class CameraMonitor:
    def __init__(self, db, interval=POLL_INTERVAL):
        self.db = db
        self.interval = interval
        self._state = {}
        self._lock = threading.Lock()
        self._thread = None
        self._stop = threading.Event()
        self._last_poll = None

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="camera-monitor", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception:
                logger.exception("Camera poll failed")
            self._stop.wait(self.interval)

    def poll_once(self):
        cameras = self.db.get_all_cameras(status=None)
        results = {}
        for camera in cameras:
            camera_id = camera["camera_id"]
            status = probe_camera(camera.get("ip_address"), camera.get("rtsp_port"))
            entry = {
                "stream_status": status,
                "checked_at": datetime.now().isoformat(timespec="seconds"),
                "source": "recording" if status == "unconfigured" else "rtsp",
                "fps": 0.0,
            }
            if status == "online":
                entry["last_seen"] = entry["checked_at"]
            else:
                previous = self._state.get(camera_id, {})
                entry["last_seen"] = previous.get("last_seen") or camera.get("last_seen") or ""
            results[camera_id] = entry
            if status != camera.get("stream_status"):
                self.db.update_camera_stream(camera_id, status, entry["last_seen"] or None)

        with self._lock:
            self._state = results
            self._last_poll = datetime.now()
        return results

    def state_for(self, camera_id):
        with self._lock:
            return dict(self._state.get(camera_id, {}))

    def snapshot(self):
        with self._lock:
            return {
                "cameras": {k: dict(v) for k, v in self._state.items()},
                "last_poll": self._last_poll.isoformat(timespec="seconds") if self._last_poll else None,
                "interval_seconds": self.interval,
            }

    def wait_for_first_poll(self, timeout=5.0):
        """Block briefly so the first dashboard request has real data."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if self._last_poll is not None:
                    return True
            time.sleep(0.1)
        return False
