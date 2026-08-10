"""Process-wide singletons shared by every router.

The detection models are expensive to load, so `HelmetDetectionSystem` is
created lazily on the first analysis and then reused. Everything else (the
database handle, the config module) is cheap and created eagerly.
"""

import logging
import threading
from pathlib import Path

import config as cfg
from database import DatabaseManager

logger = logging.getLogger(__name__)

DB_PATH = cfg.DATABASE_DIR / "violations.db"
UPLOADS_DIR = cfg.OUTPUT_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Directories a client is allowed to read media from. Any path outside this
# set is rejected, so a stored path can never be used to walk the filesystem.
MEDIA_ROOTS = {
    "evidence": cfg.IMAGES_DIR,
    "poster": cfg.WARNING_POSTERS_DIR,
    "report": cfg.REPORTS_DIR,
    "upload": UPLOADS_DIR,
}

_db = DatabaseManager(DB_PATH, seed_defaults=cfg.DB_SEED_DEFAULTS)
_system = None
_system_lock = threading.Lock()
_system_error = None


_camera_monitor = None


def get_db():
    return _db


def get_camera_monitor():
    global _camera_monitor
    if _camera_monitor is None:
        from .services.camera_monitor import CameraMonitor

        _camera_monitor = CameraMonitor(_db)
    return _camera_monitor


def get_config():
    return cfg


def system_state():
    """Report whether the AI engine is loaded, without forcing a load."""
    return {
        "loaded": _system is not None,
        "error": _system_error,
    }


def get_system():
    """Load the detection system on first use (blocking, thread-safe)."""
    global _system, _system_error
    if _system is not None:
        return _system
    with _system_lock:
        if _system is None:
            from app import HelmetDetectionSystem

            logger.info("Loading detection models...")
            try:
                _system = HelmetDetectionSystem()
                _system_error = None
                logger.info("Detection models ready")
            except Exception as exc:  # surfaced on the System Health page
                _system_error = str(exc)
                logger.exception("Detection system failed to load")
                raise
    return _system


def resolve_media(kind, name):
    """Map a (kind, filename) pair to a real file inside an allowed root.

    Returns None when the kind is unknown, the name escapes the root, or the
    file does not exist.
    """
    root = MEDIA_ROOTS.get(kind)
    if root is None or not name:
        return None
    candidate = (Path(root) / name).resolve()
    try:
        candidate.relative_to(Path(root).resolve())
    except ValueError:
        logger.warning(f"Rejected media path outside {kind} root: {name!r}")
        return None
    return candidate if candidate.is_file() else None


def media_ref(kind, stored_path):
    """Turn an absolute path stored in the database into a client-safe name."""
    if not stored_path:
        return None
    name = Path(stored_path).name
    return name if resolve_media(kind, name) else None
