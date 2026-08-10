"""Background analysis jobs for uploaded CCTV footage.

One video is analyzed at a time: the YOLO models hold GPU/CPU memory and
running several passes concurrently would make the reported processing FPS
meaningless. Extra requests queue behind the running job.
"""

import logging
import threading
import uuid
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from queue import Queue

import cv2

from ..state import UPLOADS_DIR, get_config, get_db, get_system

logger = logging.getLogger(__name__)

VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
MAX_JOB_HISTORY = 50


def probe_video(path):
    """Read container metadata. Returns zeros when the file is unreadable."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    cap.release()
    return {
        "fps": round(fps, 2),
        "total_frames": frames,
        "width": width,
        "height": height,
        "duration_seconds": round(frames / fps, 1) if fps > 0 else 0.0,
        "resolution": f"{width} x {height}" if width and height else "unknown",
    }


class AnalysisJob:
    """State machine for a single analysis: queued -> running -> completed."""

    def __init__(self, job_id, upload):
        self.job_id = job_id
        self.upload = upload
        self.status = "queued"
        self.created_at = datetime.now()
        self.started_at = None
        self.finished_at = None
        self.error = None
        self.result = None
        self.cancel_requested = False
        self.camera = {}
        self.progress = {
            "frames_total": upload.get("total_frames", 0),
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

    def to_dict(self):
        return {
            "job_id": self.job_id,
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at.isoformat(timespec="seconds"),
            "started_at": self.started_at.isoformat(timespec="seconds") if self.started_at else None,
            "finished_at": self.finished_at.isoformat(timespec="seconds") if self.finished_at else None,
            "video": {
                "upload_id": self.upload.get("upload_id"),
                "filename": self.upload.get("filename"),
                "size_bytes": self.upload.get("size_bytes", 0),
                "duration_seconds": self.upload.get("duration_seconds", 0.0),
                "resolution": self.upload.get("resolution", "unknown"),
                "fps": self.upload.get("fps", 0.0),
                "total_frames": self.upload.get("total_frames", 0),
            },
            "camera": self.camera,
            "progress": dict(self.progress),
            "result": self.result,
        }


class AnalysisManager:
    def __init__(self):
        self._uploads = OrderedDict()
        self._jobs = OrderedDict()
        self._lock = threading.Lock()
        self._queue = Queue()
        self._worker = None

    # ------------------------------------------------------------------
    # Uploads
    # ------------------------------------------------------------------
    def register_upload(self, filename, data):
        suffix = Path(filename).suffix.lower()
        if suffix not in VIDEO_SUFFIXES:
            raise ValueError(
                f"Unsupported format '{suffix or filename}'. "
                f"Allowed: {', '.join(sorted(VIDEO_SUFFIXES))}"
            )

        upload_id = uuid.uuid4().hex[:12]
        # Store under a generated name so a hostile filename cannot influence
        # the path; the original is kept as display metadata only.
        stored = UPLOADS_DIR / f"{upload_id}{suffix}"
        stored.write_bytes(data)

        meta = probe_video(stored)
        if meta is None:
            stored.unlink(missing_ok=True)
            raise ValueError("The file could not be decoded as video")

        upload = {
            "upload_id": upload_id,
            "filename": Path(filename).name,
            "stored_name": stored.name,
            "path": str(stored),
            "size_bytes": len(data),
            "uploaded_at": datetime.now().isoformat(timespec="seconds"),
            **meta,
        }
        with self._lock:
            self._uploads[upload_id] = upload
        logger.info(f"Upload registered: {upload['filename']} ({upload_id})")
        return upload

    def get_upload(self, upload_id):
        with self._lock:
            return self._uploads.get(upload_id)

    @staticmethod
    def public_upload(upload):
        """Strip the server-side path — the client never needs the filesystem."""
        return {k: v for k, v in upload.items() if k != "path"}

    def list_uploads(self):
        with self._lock:
            return [self.public_upload(u) for u in reversed(self._uploads.values())]

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------
    def submit(self, upload_id, camera=None):
        upload = self.get_upload(upload_id)
        if upload is None:
            raise KeyError(upload_id)

        job = AnalysisJob(uuid.uuid4().hex[:12], upload)
        job.camera = camera or {}
        with self._lock:
            self._jobs[job.job_id] = job
            while len(self._jobs) > MAX_JOB_HISTORY:
                self._jobs.popitem(last=False)
        self._queue.put(job.job_id)
        self._ensure_worker()
        logger.info(f"Analysis queued: {upload['filename']} (job {job.job_id})")
        return job

    def get_job(self, job_id):
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self):
        with self._lock:
            return list(reversed(self._jobs.values()))

    def active_job(self):
        with self._lock:
            for job in reversed(self._jobs.values()):
                if job.status in ("queued", "running"):
                    return job
        return None

    def cancel(self, job_id):
        job = self.get_job(job_id)
        if job is None:
            return None
        if job.status in ("completed", "failed", "cancelled"):
            return job
        job.cancel_requested = True
        if job.status == "queued":
            job.status = "cancelled"
            job.finished_at = datetime.now()
        return job

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------
    def _ensure_worker(self):
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = threading.Thread(
                target=self._run_forever, name="analysis-worker", daemon=True
            )
            self._worker.start()

    def _run_forever(self):
        while True:
            job_id = self._queue.get()
            try:
                job = self.get_job(job_id)
                if job is not None and not job.cancel_requested:
                    self._run_job(job)
            except Exception:
                logger.exception(f"Analysis worker crashed on job {job_id}")
            finally:
                self._queue.task_done()

    def _run_job(self, job):
        job.status = "running"
        job.started_at = datetime.now()
        cfg = get_config()

        try:
            system = get_system()
            result = system.process_video(
                job.upload["path"],
                camera_name=job.camera.get("camera_name"),
                camera_id=job.camera.get("camera_id"),
                location=job.camera.get("location"),
                progress_callback=lambda payload: job.progress.update(payload),
                analysis_id=job.job_id,
                should_stop=lambda: job.cancel_requested,
                display_name=job.upload["filename"],
            )
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            job.finished_at = datetime.now()
            logger.exception(f"Analysis failed for job {job.job_id}")
            return

        job.finished_at = datetime.now()
        job.status = "cancelled" if result.get("cancelled") else "completed"
        job.camera = {
            "camera_id": result.get("camera_id", ""),
            "camera_name": result.get("camera_name", ""),
            "location": result.get("location", ""),
        }
        job.result = {
            "video_name": result.get("video_name"),
            "total_frames": result.get("total_frames", 0),
            "frames_analyzed": result.get("frames_processed", 0),
            "video_fps": result.get("video_fps", 0.0),
            "people_detected": result.get("people_detected", 0),
            "person_frames": result.get("person_frames", 0),
            "compliant_frames": result.get("compliant_frames", 0),
            # The headline pair the operator is meant to compare.
            "raw_detections": result.get("raw_detections", 0),
            "unique_incidents": result.get("violations", 0),
            "elapsed_seconds": round(result.get("elapsed_seconds", 0.0), 1),
            "processing_fps": round(result.get("processing_fps", 0.0), 1),
            "incident_ids": [i["incident_id"] for i in result.get("incidents", [])],
            "report_available": bool(result.get("report_path")),
            "report_name": Path(result["report_path"]).name if result.get("report_path") else None,
            "frame_skip": int(getattr(cfg, "FRAME_SKIP", 1)),
        }
        self._persist_run(job)
        logger.info(
            f"Analysis {job.status} for job {job.job_id}: "
            f"{job.result['unique_incidents']} incidents from "
            f"{job.result['raw_detections']} raw detections"
        )

    @staticmethod
    def _persist_run(job):
        """Store run totals so compliance rate survives a restart."""
        try:
            get_db().save_analysis_run({
                "run_id": job.job_id,
                "video_name": job.result["video_name"],
                "source_type": "recording",
                "camera_id": job.camera.get("camera_id", ""),
                "camera_name": job.camera.get("camera_name", ""),
                "location": job.camera.get("location", ""),
                "started_at": job.started_at.isoformat(timespec="seconds"),
                "finished_at": job.finished_at.isoformat(timespec="seconds"),
                "date": job.finished_at.strftime("%Y-%m-%d"),
                "total_frames": job.result["total_frames"],
                "frames_analyzed": job.result["frames_analyzed"],
                "people_detected": job.result["people_detected"],
                "person_frames": job.result["person_frames"],
                "compliant_frames": job.result["compliant_frames"],
                "raw_detections": job.result["raw_detections"],
                "unique_incidents": job.result["unique_incidents"],
                "elapsed_seconds": job.result["elapsed_seconds"],
                "processing_fps": job.result["processing_fps"],
                "status": job.status,
            })
        except Exception:
            logger.exception(f"Could not persist analysis run {job.job_id}")


analysis_manager = AnalysisManager()
