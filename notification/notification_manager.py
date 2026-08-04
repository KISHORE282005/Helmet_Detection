import cv2
import logging
from datetime import datetime
from pathlib import Path

from database import DatabaseManager, RuleManager
from .email_service import EmailService, STATUS_FAILED, STATUS_SENT, STATUS_SKIPPED

logger = logging.getLogger(__name__)


class NotificationManager:
    """Supervisor notification pipeline, fully independent of the AI module.

    Consumes a confirmed violation (incident dict + evidence frame) and
    performs: camera lookup -> supervisor lookup -> rule lookup ->
    violation record -> temp screenshot -> email (attach + retry) ->
    email log -> temp cleanup. A failure here NEVER affects monitoring.
    """

    def __init__(self, config, db=None, email_service=None):
        self.config = config
        self.db = db or DatabaseManager(config.DATABASE_DIR / "violations.db")
        self.rule_manager = RuleManager(self.db)
        self.email_service = email_service or EmailService(config)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def notify(self, incident, frame):
        """Process one confirmed violation. Always safe to call.

        `incident` is the dict produced by the report generator (contains
        camera_id, camera_name, location, video_name, date, timestamp,
        track_id, image_path, ...). `frame` is the BGR evidence frame.
        Returns the VIOLATION_HISTORY id, or None on failure.
        """
        try:
            camera = self.db.get_camera(incident.get("camera_id") or "")
            supervisor = self._resolve_supervisor(incident, camera)
            rule = self.rule_manager.resolve_rule(incident.get("violation_type", "Helmet Missing"))
            duration = self._compute_duration(incident, rule)

            violation_id = self.db.record_violation({
                "track_id": incident.get("track_id", 0),
                "camera_id": (camera or {}).get("camera_id") or incident.get("camera_id", ""),
                "supervisor_id": (supervisor or {}).get("supervisor_id", ""),
                "rule_id": (rule or {}).get("rule_id", ""),
                "violation_type": incident.get("violation_type", "Helmet Missing"),
                "date": incident.get("date", datetime.now().strftime("%Y-%m-%d")),
                "time": incident.get("timestamp", datetime.now().strftime("%H:%M:%S")),
                "duration": duration,
                "screenshot_path": incident.get("image_path", ""),
                "status": "Open",
                "remarks": "",
            })
            logger.info(f"VIOLATION_HISTORY | {violation_id} recorded (track {incident.get('track_id')})")

            if not supervisor or not supervisor.get("email"):
                self.db.log_email({
                    "violation_id": violation_id,
                    "supervisor_id": (supervisor or {}).get("supervisor_id", ""),
                    "email_address": (supervisor or {}).get("email", ""),
                    "delivery_status": STATUS_SKIPPED,
                    "remarks": "no supervisor/email mapped for camera "
                               f"{incident.get('camera_id')}",
                })
                logger.warning(
                    f"No supervisor mapped for camera {incident.get('camera_id')}; "
                    f"notification skipped (violation {violation_id} recorded)"
                )
                return violation_id

            self._send_notification(incident, frame, camera, supervisor, rule, violation_id, duration)
            return violation_id
        except Exception as exc:
            logger.exception(f"Notification pipeline failed: {exc}")
            return None

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------
    def _resolve_supervisor(self, incident, camera):
        supervisor = None
        if camera:
            supervisor = self.db.get_supervisor(camera.get("supervisor_id"))
        if not supervisor:
            fallback = self.config.DEFAULT_SUPERVISOR_ID
            if fallback:
                supervisor = self.db.get_supervisor(fallback)
        return supervisor

    def _send_notification(self, incident, frame, camera, supervisor, rule, violation_id, duration):
        screenshot = self._save_screenshot(frame, violation_id)
        subject = self.config.EMAIL_SUBJECT
        body = self._build_email_body(incident, camera, supervisor, rule, duration)
        status, retries, remarks = self.email_service.send(
            supervisor["email"], subject, body, screenshot
        )

        if status == STATUS_SENT:
            self._delete_screenshot(screenshot)
            remarks = "OK"
        else:
            logger.warning(
                f"Email delivery {status} for {violation_id} to {supervisor['email']}; "
                f"screenshot retained at {screenshot}"
            )

        self.db.log_email({
            "violation_id": violation_id,
            "supervisor_id": supervisor.get("supervisor_id", ""),
            "email_address": supervisor.get("email", ""),
            "delivery_status": status,
            "retry_count": retries,
            "remarks": remarks,
        })

        if status == STATUS_SENT:
            self.db.update_violation_status(violation_id, "Notified")
        elif status == STATUS_FAILED:
            self.db.update_violation_status(
                violation_id, "Failed",
                remarks=f"delivery failed after {retries} retries: {remarks}",
            )
        logger.info(
            f"NOTIFICATION | {violation_id} -> {supervisor['email']} "
            f"[{status}] retries={retries} screenshot={Path(screenshot).name if screenshot else 'n/a'}"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _save_screenshot(self, frame, violation_id):
        if frame is None or frame.size == 0:
            return None
        directory = Path(self.config.EMAIL_TEMP_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = directory / f"violation_{violation_id}_{stamp}.jpg"
        ok = cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, self.config.EMAIL_IMAGE_QUALITY])
        if not ok:
            logger.warning(f"Failed to write temp screenshot {path}")
            return None
        logger.info(f"Temp screenshot saved: {path}")
        return str(path)

    def _delete_screenshot(self, screenshot):
        if not screenshot:
            return
        try:
            Path(screenshot).unlink(missing_ok=True)
            logger.info(f"Temp screenshot deleted: {screenshot}")
        except Exception as exc:
            logger.warning(f"Could not delete temp screenshot {screenshot}: {exc}")

    def _compute_duration(self, incident, rule):
        fps = float(incident.get("fps") or 0)
        frames = float(getattr(self.config, "VIOLATION_REQUIRED_FRAMES", 30))
        if fps > 0:
            return f"{frames / fps:.1f} s"
        if rule and rule.get("threshold"):
            threshold = str(rule["threshold"])
            if threshold.replace(".", "").isdigit():
                unit = rule.get("threshold_type") or "s"
                return f"{threshold} {unit}"
        return f"{int(frames)} frames"

    def _build_email_body(self, incident, camera, supervisor, rule, duration):
        rule_name = (rule or {}).get("rule_name") or incident.get("violation_type", "Helmet Missing")
        camera_name = (camera or {}).get("camera_name") or incident.get("camera_name", "Unknown")
        camera_id = (camera or {}).get("camera_id") or incident.get("camera_id", "")
        department = (camera or {}).get("department") or (supervisor or {}).get("department", "")
        area = (camera or {}).get("area") or incident.get("location", "")

        return (
            f"Dear {supervisor.get('supervisor_name', 'Supervisor')},\n\n"
            "The AI Safety Monitoring System has detected a safety violation.\n\n"
            "Violation Details\n"
            f"Rule: {rule_name}\n"
            f"Camera: {camera_name} ({camera_id})\n"
            f"Department: {department}\n"
            f"Area: {area}\n"
            f"Date: {incident.get('date', '')}\n"
            f"Time: {incident.get('timestamp', '')}\n"
            f"Track ID: {incident.get('track_id', '')}\n"
            f"Violation Duration: {duration}\n\n"
            "Please review the attached evidence.\n\n"
            "Regards\n"
            "AI Safety Monitoring System"
        )
