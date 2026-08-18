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
        # Value-stream analysis for the current run, filled in by the pipeline
        # once the video ends. Safety and productivity ship in one workbook so
        # a supervisor reads one file, not two.
        self.nva_segments = []
        self.nva_breakdown = None
        self.db = DatabaseManager(config.DATABASE_DIR / "violations.db")

    def add_incident(self, incident):
        # IDs come from the database, not from len(self.incidents): a per-run
        # counter would restart at INC0001 every analysis and the INSERT OR
        # REPLACE would silently overwrite earlier incidents.
        incident_id = self.db.next_incident_id()
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
            "detected_at": incident.get(
                "detected_at", datetime.now().isoformat(timespec="seconds")
            ),
            "analysis_id": incident.get("analysis_id", ""),
            "confirm_frames": incident.get("confirm_frames", 0),
        }
        self.incidents.append(record)
        self._save_to_database(record)
        logger.info(f"Incident {incident_id} recorded for Track ID {record['track_id']}")
        return record

    def _save_to_database(self, record):
        try:
            self.db.insert_violation(record)
        except Exception as e:
            logger.error(f"Database save failed: {e}")

    def generate_excel_report(self, video_name="Unknown"):
        if not self.incidents and not self.nva_segments:
            logger.info("No incidents or activity segments to report")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = Path(video_name).stem
        report_path = self.config.REPORTS_DIR / f"Safety_Report_{safe_name}_{timestamp}.xlsx"

        with pd.ExcelWriter(str(report_path), engine="openpyxl") as writer:
            if self.incidents:
                self._write_sheet(writer, "Violations", self._violations_frame())
            for name, frame in self._nva_frames():
                self._write_sheet(writer, name, frame)

        logger.info(f"Excel report generated: {report_path}")
        return str(report_path)

    def _violations_frame(self):
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
        return df

    def _nva_frames(self):
        """The value-stream sheets: summary, raw segments, recommendations."""
        sheets = []
        breakdown = self.nva_breakdown or {}

        if breakdown.get("classified_seconds"):
            summary_rows = [
                {"Metric": "Observed operator time", "Value": breakdown["observed_duration"],
                 "Seconds": breakdown["observed_seconds"], "Share": ""},
                {"Metric": "Classified time", "Value": breakdown["classified_duration"],
                 "Seconds": breakdown["classified_seconds"], "Share": ""},
                {"Metric": "People analysed", "Value": breakdown.get("tracks", 0),
                 "Seconds": "", "Share": ""},
            ]
            summary_rows += [
                {
                    "Metric": row["label"],
                    "Value": row["duration"],
                    "Seconds": row["seconds"],
                    "Share": f"{row['share']:.1f}%",
                }
                for row in breakdown["value_split"]
            ]
            sheets.append(("Value Stream", pd.DataFrame(summary_rows)))

            activity_rows = [
                {
                    "Activity": row["label"],
                    "Classification": row["value_class"],
                    "Lean Waste": row["waste"] or "—",
                    "Duration": row["duration"],
                    "Seconds": row["seconds"],
                    "Share": f"{row['share']:.1f}%",
                    "Occurrences": row["occurrences"],
                    "Average Length (s)": row["avg_seconds"],
                    "Why It Is Classified This Way": row["description"],
                }
                for row in breakdown["by_activity"]
            ]
            if activity_rows:
                sheets.append(("Activity Breakdown", pd.DataFrame(activity_rows)))

        if self.nva_segments:
            segment_rows = [
                {
                    "Camera ID": segment.get("camera_id", ""),
                    "Camera Name": segment.get("camera_name", ""),
                    "Location": segment.get("location", ""),
                    "Video Name": segment.get("video_name", ""),
                    "Track ID": segment.get("track_id", 0),
                    "Activity": segment.get("label", segment.get("activity", "")),
                    "Classification": segment.get("value_class", ""),
                    "Lean Waste": segment.get("waste") or "—",
                    "Start": segment.get("start_time", ""),
                    "End": segment.get("end_time", ""),
                    "Duration (s)": segment.get("duration_seconds", 0.0),
                    "Confidence": segment.get("confidence", 0.0),
                }
                for segment in self.nva_segments
            ]
            sheets.append(("NVA Activities", pd.DataFrame(segment_rows)))

        recommendations = breakdown.get("recommendations") or []
        if recommendations:
            sheets.append(("Recommendations", pd.DataFrame([
                {
                    "Priority": index,
                    "Severity": action["severity"].upper(),
                    "Recommendation": action["title"],
                    "Lean Waste": action.get("waste") or "—",
                    "Observed": action["observation"],
                    "Share of Time": f"{action['share']:.1f}%",
                    "Likely Root Causes": "\n".join(action["root_causes"]),
                    "Actions": "\n".join(f"{i}. {step}" for i, step in enumerate(action["actions"], 1)),
                    "Lean Tool": action["lean_tool"],
                    "Expected Impact": action["expected_impact"],
                    "How To Verify": action["verify"],
                }
                for index, action in enumerate(recommendations, 1)
            ])))

        return sheets

    @staticmethod
    def _write_sheet(writer, name, frame):
        frame.to_excel(writer, sheet_name=name, index=False)
        sheet = writer.sheets[name]
        for col in sheet.columns:
            # Multi-line cells (action lists) would otherwise force a column
            # as wide as the whole paragraph.
            longest = max(
                (len(line) for cell in col for line in str(cell.value or "").split("\n")),
                default=0,
            )
            sheet.column_dimensions[col[0].column_letter].width = min(longest + 2, 60)

    def get_incident_count(self):
        return len(self.incidents)
