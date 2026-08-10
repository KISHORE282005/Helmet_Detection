"""Recorded-video analysis: upload, run, watch progress, read results.

All numbers reported here come from the running pipeline. Nothing is
simulated: before a job starts, its counters are zero.
"""

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..schemas import AnalysisStart
from ..services import analysis_manager
from ..state import get_config, get_db

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

# Tunable from .env — see API_MAX_UPLOAD_MB.
MAX_UPLOAD_MB = int(getattr(get_config(), "API_MAX_UPLOAD_MB", 2048))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


@router.post("/upload", status_code=201)
async def upload_video(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="The uploaded file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {MAX_UPLOAD_MB} MB upload limit",
        )
    try:
        upload = analysis_manager.register_upload(file.filename or "video.mp4", data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return analysis_manager.public_upload(upload)


@router.get("/uploads")
def list_uploads():
    return {"items": analysis_manager.list_uploads()}


@router.post("/start", status_code=202)
def start_analysis(payload: AnalysisStart):
    db = get_db()
    camera = {}
    if payload.camera_id:
        record = db.get_camera(payload.camera_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"Camera {payload.camera_id} not found")
        camera = {
            "camera_id": record["camera_id"],
            "camera_name": payload.camera_name or record.get("camera_name"),
            "location": payload.location or record.get("location") or record.get("area"),
        }
    else:
        # Left blank, the pipeline derives camera details from the filename or
        # falls back to the configured defaults.
        camera = {
            "camera_id": None,
            "camera_name": payload.camera_name,
            "location": payload.location,
        }

    try:
        job = analysis_manager.submit(payload.upload_id, camera)
    except KeyError:
        raise HTTPException(status_code=404, detail="Upload not found — upload the video again")
    return job.to_dict()


@router.get("")
def list_jobs():
    active = analysis_manager.active_job()
    return {
        "items": [j.to_dict() for j in analysis_manager.list_jobs()],
        "active_job_id": active.job_id if active else None,
    }


@router.get("/{job_id}")
def get_job(job_id: str):
    job = analysis_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Analysis job {job_id} not found")
    return job.to_dict()


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str):
    job = analysis_manager.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Analysis job {job_id} not found")
    return job.to_dict()


@router.get("/{job_id}/incidents")
def job_incidents(job_id: str):
    from ..schemas import serialize_incident

    rows = get_db().query_incidents({"analysis_id": job_id}, limit=500)
    return {"items": [serialize_incident(r) for r in rows], "total": len(rows)}
