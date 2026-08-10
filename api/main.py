"""SafeVision AI — FastAPI application factory.

Run with:  python -m api            (or: uvicorn api.main:app --reload)
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# The pipeline modules (app, config, database, ...) live at the project root.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

import config as cfg  # noqa: E402

from .routers import ROUTERS  # noqa: E402
from .state import get_camera_monitor, get_db  # noqa: E402

logger = logging.getLogger(__name__)

FRONTEND_DIST = ROOT / "frontend" / "dist"


def _cors_origins():
    """Browser origins allowed to call the API, from API_CORS_ORIGINS in .env."""
    raw = getattr(cfg, "API_CORS_ORIGINS", "") or ""
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    provision_primary_camera()
    monitor = get_camera_monitor()
    monitor.start()
    logger.info("SafeVision AI API ready")
    yield
    monitor.stop()


def create_app():
    logging.basicConfig(
        level=getattr(logging, cfg.LOG_LEVEL, logging.INFO),
        format=cfg.LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(cfg.LOGS_DIR / "api.log", mode="a", encoding="utf-8"),
        ],
    )

    app = FastAPI(
        title="SafeVision AI",
        description="AI-Powered Industrial PPE Safety Monitoring",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router in ROUTERS:
        app.include_router(router)

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/api/health", tags=["system"])
    def liveness():
        return {"status": "ok", "service": "SafeVision AI"}

    _mount_frontend(app)
    return app


def provision_primary_camera():
    """Register (or update) the camera described by CAMERA_IP in .env.

    Lets an operator bring a camera online by editing one line, without
    touching the dashboard. Fields the user has since edited in the UI are
    preserved — only the address details are kept in step. No credentials are
    written: those stay in .env and never enter the database.
    """
    ip_address = (getattr(cfg, "CAMERA_IP", "") or "").strip()
    if not ip_address:
        return None

    camera_id = (getattr(cfg, "CAMERA_ID", "") or "CAM001").strip()
    db = get_db()
    existing = db.get_camera(camera_id) or {}

    record = {
        "camera_id": camera_id,
        "camera_name": existing.get("camera_name") or cfg.CAMERA_NAME,
        "department": existing.get("department") or cfg.CAMERA_DEPARTMENT,
        "area": existing.get("area") or cfg.CAMERA_LOCATION,
        "location": existing.get("location") or cfg.CAMERA_LOCATION,
        "supervisor_id": existing.get("supervisor_id") or cfg.CAMERA_SUPERVISOR_ID,
        "status": existing.get("status") or "Active",
        # These follow .env, so changing the address there moves the camera.
        "ip_address": ip_address,
        "rtsp_port": int(getattr(cfg, "RTSP_DEFAULT_PORT", 554)),
        "rtsp_channel": str(getattr(cfg, "CAMERA_CHANNEL", "") or ""),
        "target_fps": int(getattr(cfg, "CAMERA_TARGET_FPS", 0)),
        "ai_enabled": bool(existing.get("ai_enabled", 1)),
        "stream_status": existing.get("stream_status", "unknown"),
        "last_seen": existing.get("last_seen", ""),
    }

    db.upsert_camera(record)
    action = "updated" if existing else "registered"
    logger.info(f"Primary camera {action} from .env: {camera_id} at {ip_address}")
    return camera_id


def _mount_frontend(app):
    """Serve the built dashboard when it exists, so one process runs everything.

    In development the Vite server owns the UI and proxies /api here, so a
    missing dist/ is normal rather than an error.
    """
    if not FRONTEND_DIST.is_dir():
        @app.get("/", include_in_schema=False)
        def no_frontend():
            return JSONResponse({
                "service": "SafeVision AI API",
                "frontend": "not built",
                "hint": "Run `npm install && npm run build` in frontend/, "
                        "or `npm run dev` for the development server.",
                "docs": "/docs",
            })
        return

    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    index = FRONTEND_DIST / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        # An unmatched /api/* path is a client error, not a page. Without this
        # the catch-all would answer 200 text/html and the frontend would fail
        # trying to parse the page as JSON.
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Endpoint not found"})

        # Everything else is a client-side route and falls back to index.html.
        candidate = (FRONTEND_DIST / full_path).resolve()
        try:
            candidate.relative_to(FRONTEND_DIST.resolve())
        except ValueError:
            return FileResponse(index)
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
