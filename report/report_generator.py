import logging
import pandas as pd
from datetime import datetime
from pathlib import Path

from database import DatabaseManager

logger = logging.getLogger(__name__)


class ReportGenerator:
    def __init__(self, config):
        self.config = config
        self.incidents = []
        self.db = DatabaseManager(config.DATABASE_DIR / "violations.db")

    def add_incident(self, incident):
        incident_id = f"INC{len(self.incidents) + 1:04d}"
        record = {
            "incident_id": incident_id,
            "camera_name": incident.get("camera_name", self.config.DEFAULT_CAMERA_NAME),
            "camera_id": incident.get("camera_id", self.config.DEFAULT_CAMERA_ID),
            "location": incident.get("location", self.config.DEFAULT_LOCATION),
            "video_name": incident.get("video_name", "Unknown"),
            "image_path": incident.get("image_path", ""),
            "poster_path": incident.get("poster_path", ""),
            "timestamp": incident.get("timestamp", datetime.now().strftime("%H:%M:%S")),
            "date": incident.get("date", datetime.now().strftime("%Y-%m-%d")),
            "violation_type": "Helmet Missing",
            "confidence": incident.get("confidence", 0.0),
            "track_id": incident.get("track_id", 0),
            "scene_persons": incident.get("scene_persons", 0),
            "scene_helmet": incident.get("scene_helmet", 0),
            "scene_no_helmet": incident.get("scene_no_helmet", 0),
            "status": "Open",
        }
        self.incidents.append(record)
        self._save_to_database(record)
        logger.info(f"Incident {incident_id} recorded for Track ID {record['track_id']}")

    def _save_to_database(self, record):
        try:
            self.db.insert_violation(record)
        except Exception as e:
            logger.error(f"Database save failed: {e}")

    def generate_excel_report(self, video_name="Unknown"):
        if not self.incidents:
            logger.info("No incidents to report")
            return None

        df = pd.DataFrame(self.incidents)
        columns = [
            "incident_id", "camera_name", "camera_id", "location",
            "video_name", "image_path", "poster_path", "timestamp", "date",
            "violation_type", "confidence", "track_id", "status",
            "scene_persons", "scene_helmet", "scene_no_helmet",
        ]
        df = df[columns]
        df.columns = [
            "Incident ID", "Camera Name", "Camera ID", "Location",
            "Video Name", "Violation Image", "Warning Poster", "Timestamp", "Date",
            "Violation Type", "Confidence Score", "Track ID", "Status",
            "Persons in Frame", "With Helmet", "Without Helmet",
        ]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = Path(video_name).stem
        report_path = self.config.REPORTS_DIR / f"Safety_Report_{safe_name}_{timestamp}.xlsx"

        with pd.ExcelWriter(str(report_path), engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Violations", index=False)
            sheet = writer.sheets["Violations"]
            for col in sheet.columns:
                max_len = max(len(str(cell.value or "")) for cell in col) + 2
                sheet.column_dimensions[col[0].column_letter].width = min(max_len, 50)

        logger.info(f"Excel report generated: {report_path}")
        return str(report_path)

    def get_incident_count(self):
        return len(self.incidents)
