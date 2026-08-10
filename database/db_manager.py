import logging
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema: notification & monitoring tables
# ---------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS violations (
    incident_id TEXT PRIMARY KEY,
    camera_name TEXT,
    camera_id TEXT,
    location TEXT,
    video_name TEXT,
    image_path TEXT,
    poster_path TEXT DEFAULT '',
    timestamp TEXT,
    date TEXT,
    violation_type TEXT,
    confidence REAL,
    track_id INTEGER,
    scene_persons INTEGER DEFAULT 0,
    scene_helmet INTEGER DEFAULT 0,
    scene_no_helmet INTEGER DEFAULT 0,
    status TEXT DEFAULT 'Open'
);

CREATE TABLE IF NOT EXISTS supervisor_master (
    supervisor_id TEXT PRIMARY KEY,
    supervisor_name TEXT NOT NULL,
    department TEXT,
    email TEXT,
    phone_number TEXT,
    status TEXT DEFAULT 'Active'
);

CREATE TABLE IF NOT EXISTS camera_master (
    camera_id TEXT PRIMARY KEY,
    camera_name TEXT NOT NULL,
    department TEXT,
    area TEXT,
    supervisor_id TEXT,
    status TEXT DEFAULT 'Active',
    FOREIGN KEY (supervisor_id) REFERENCES supervisor_master(supervisor_id)
);

CREATE TABLE IF NOT EXISTS rule_master (
    rule_id TEXT PRIMARY KEY,
    rule_name TEXT NOT NULL,
    threshold TEXT,
    threshold_type TEXT,
    priority TEXT,
    status TEXT DEFAULT 'Active'
);

CREATE TABLE IF NOT EXISTS violation_history (
    violation_id TEXT PRIMARY KEY,
    track_id INTEGER,
    camera_id TEXT,
    supervisor_id TEXT,
    rule_id TEXT,
    violation_type TEXT,
    date TEXT,
    time TEXT,
    duration TEXT,
    screenshot_path TEXT,
    status TEXT DEFAULT 'Open',
    remarks TEXT
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    run_id TEXT PRIMARY KEY,
    video_name TEXT,
    source_type TEXT DEFAULT 'recording',
    camera_id TEXT,
    camera_name TEXT,
    location TEXT,
    started_at TEXT,
    finished_at TEXT,
    date TEXT,
    total_frames INTEGER DEFAULT 0,
    frames_analyzed INTEGER DEFAULT 0,
    people_detected INTEGER DEFAULT 0,
    person_frames INTEGER DEFAULT 0,
    compliant_frames INTEGER DEFAULT 0,
    raw_detections INTEGER DEFAULT 0,
    unique_incidents INTEGER DEFAULT 0,
    elapsed_seconds REAL DEFAULT 0,
    processing_fps REAL DEFAULT 0,
    status TEXT DEFAULT 'completed'
);

CREATE TABLE IF NOT EXISTS email_log (
    email_log_id TEXT PRIMARY KEY,
    violation_id TEXT,
    supervisor_id TEXT,
    email_address TEXT,
    sent_time TEXT,
    delivery_status TEXT,
    retry_count INTEGER DEFAULT 0,
    remarks TEXT
);
"""

MIGRATIONS = {
    "violations": [
        ("scene_persons", "INTEGER DEFAULT 0"),
        ("scene_helmet", "INTEGER DEFAULT 0"),
        ("scene_no_helmet", "INTEGER DEFAULT 0"),
        ("poster_path", "TEXT DEFAULT ''"),
        # Wall-clock moment the incident was written (ISO 8601). `timestamp`
        # stays the offset inside the source video.
        ("detected_at", "TEXT DEFAULT ''"),
        # Analysis run that produced this incident (empty for live streams).
        ("analysis_id", "TEXT DEFAULT ''"),
        # Consecutive no-helmet frames that confirmed the violation.
        ("confirm_frames", "INTEGER DEFAULT 0"),
        ("reviewed_at", "TEXT DEFAULT ''"),
        ("reviewed_by", "TEXT DEFAULT ''"),
        ("remarks", "TEXT DEFAULT ''"),
    ],
    "camera_master": [
        ("location", "TEXT DEFAULT ''"),
        ("ip_address", "TEXT DEFAULT ''"),
        # Stream transport metadata only. Credentials are NEVER stored here.
        ("rtsp_port", "INTEGER DEFAULT 554"),
        ("rtsp_channel", "TEXT DEFAULT ''"),
        ("stream_status", "TEXT DEFAULT 'unknown'"),
        ("ai_enabled", "INTEGER DEFAULT 1"),
        ("target_fps", "INTEGER DEFAULT 0"),
        ("last_seen", "TEXT DEFAULT ''"),
    ],
}

INSERT_VIOLATION_SQL = """
INSERT OR REPLACE INTO violations
(incident_id, camera_name, camera_id, location, video_name,
 image_path, poster_path, timestamp, date, violation_type, confidence,
 track_id, scene_persons, scene_helmet, scene_no_helmet, status,
 detected_at, analysis_id, confirm_frames)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

INSERT_SUPERVISOR_SQL = """
INSERT OR REPLACE INTO supervisor_master
(supervisor_id, supervisor_name, department, email, phone_number, status)
VALUES (?, ?, ?, ?, ?, ?)
"""

INSERT_CAMERA_SQL = """
INSERT OR REPLACE INTO camera_master
(camera_id, camera_name, department, area, supervisor_id, status,
 location, ip_address, rtsp_port, rtsp_channel, stream_status,
 ai_enabled, target_fps, last_seen)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

INSERT_RULE_SQL = """
INSERT OR REPLACE INTO rule_master
(rule_id, rule_name, threshold, threshold_type, priority, status)
VALUES (?, ?, ?, ?, ?, ?)
"""

INSERT_VIOLATION_HISTORY_SQL = """
INSERT INTO violation_history
(violation_id, track_id, camera_id, supervisor_id, rule_id, violation_type,
 date, time, duration, screenshot_path, status, remarks)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

INSERT_EMAIL_LOG_SQL = """
INSERT INTO email_log
(email_log_id, violation_id, supervisor_id, email_address, sent_time,
 delivery_status, retry_count, remarks)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""


class DatabaseManager:
    """SQLite abstraction for the monitoring / notification module.

    Owns the schema for SUPERVISOR_MASTER, CAMERA_MASTER, RULE_MASTER,
    VIOLATION_HISTORY and EMAIL_LOG, plus the legacy `violations` table used
    by the report generator. Every operation opens its own connection so the
    class is safe to share across threads.
    """

    def __init__(self, db_path, seed_defaults=True):
        self.db_path = db_path
        self.initialize(seed_defaults=seed_defaults)

    # ------------------------------------------------------------------
    # Core / schema
    # ------------------------------------------------------------------
    def connect(self):
        return sqlite3.connect(str(self.db_path))

    def initialize(self, seed_defaults=True):
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.executescript(SCHEMA)
            self._migrate(cursor)
            conn.commit()
        finally:
            conn.close()
        if seed_defaults:
            from .seed_data import seed_master_data
            seed_master_data(self)
        logger.info(f"Database initialized at {self.db_path}")

    def _migrate(self, cursor):
        for table, columns in MIGRATIONS.items():
            existing = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()}
            for column, definition in columns:
                if column not in existing:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                    logger.info(f"Database migrated: added {table}.{column}")

    def execute(self, sql, params=()):
        with self.connect() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
        return cursor.rowcount

    def execute_query(self, sql, params=()):
        with self.connect() as conn:
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
        return rows

    def _fetch_dicts(self, sql, params=()):
        with self.connect() as conn:
            cursor = conn.execute(sql, params)
            columns = [d[0] for d in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _next_id(self, table, prefix, id_column):
        rows = self.execute_query(f"SELECT {id_column} FROM {table}")
        highest = 0
        for (value,) in rows:
            try:
                highest = max(highest, int(str(value).lstrip(prefix)))
            except (TypeError, ValueError):
                continue
        return f"{prefix}{highest + 1:04d}"

    # ------------------------------------------------------------------
    # Legacy violations table (report generator)
    # ------------------------------------------------------------------
    def insert_violation(self, record):
        with self.connect() as conn:
            conn.execute(INSERT_VIOLATION_SQL, (
                record["incident_id"],
                record.get("camera_name", ""),
                record.get("camera_id", ""),
                record.get("location", ""),
                record.get("video_name", "Unknown"),
                record.get("image_path", ""),
                record.get("poster_path", ""),
                record.get("timestamp", ""),
                record.get("date", datetime.now().strftime("%Y-%m-%d")),
                record.get("violation_type", "Helmet Missing"),
                record.get("confidence", 0.0),
                record.get("track_id", 0),
                record.get("scene_persons", 0),
                record.get("scene_helmet", 0),
                record.get("scene_no_helmet", 0),
                record.get("status", "Open"),
                record.get("detected_at", datetime.now().isoformat(timespec="seconds")),
                record.get("analysis_id", ""),
                record.get("confirm_frames", 0),
            ))
        return record["incident_id"]

    def next_incident_id(self):
        """Globally unique incident ID derived from the whole table.

        Must not be per-run: `INSERT OR REPLACE` would otherwise let a new
        analysis overwrite incidents recorded by an earlier one.
        """
        return self._next_id("violations", "INC", "incident_id")

    def update_status(self, incident_id, status):
        return self.execute(
            "UPDATE violations SET status = ? WHERE incident_id = ?",
            (status, incident_id),
        )

    def fetch_all(self):
        return self.execute_query("SELECT * FROM violations ORDER BY date DESC, timestamp DESC")

    def fetch_by_id(self, incident_id):
        rows = self.execute_query(
            "SELECT * FROM violations WHERE incident_id = ?", (incident_id,)
        )
        return rows[0] if rows else None

    def count(self, status=None):
        if status:
            rows = self.execute_query(
                "SELECT COUNT(*) FROM violations WHERE status = ?", (status,)
            )
        else:
            rows = self.execute_query("SELECT COUNT(*) FROM violations")
        return rows[0][0] if rows else 0

    def reset(self):
        with self.connect() as conn:
            conn.execute("DELETE FROM violations")
            conn.commit()
        logger.info("violations table cleared")

    def columns(self):
        rows = self.execute_query("PRAGMA table_info(violations)")
        return [row[1] for row in rows]

    # ------------------------------------------------------------------
    # Incident queries (dashboard / history / analytics)
    # ------------------------------------------------------------------
    @staticmethod
    def _incident_filters(filters):
        """Build a WHERE clause from a filter dict. Returns (sql, params)."""
        clauses, params = [], []
        mapping = {
            "camera_id": "camera_id = ?",
            "location": "location = ?",
            "status": "status = ?",
            "violation_type": "violation_type = ?",
            "analysis_id": "analysis_id = ?",
            "video_name": "video_name = ?",
        }
        for key, clause in mapping.items():
            value = filters.get(key)
            if value:
                clauses.append(clause)
                params.append(value)
        if filters.get("date_from"):
            clauses.append("date >= ?")
            params.append(filters["date_from"])
        if filters.get("date_to"):
            clauses.append("date <= ?")
            params.append(filters["date_to"])
        if filters.get("min_confidence") is not None:
            clauses.append("confidence >= ?")
            params.append(float(filters["min_confidence"]))
        if filters.get("search"):
            term = f"%{filters['search']}%"
            clauses.append(
                "(incident_id LIKE ? OR camera_id LIKE ? OR camera_name LIKE ?"
                " OR location LIKE ? OR video_name LIKE ?)"
            )
            params.extend([term] * 5)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        return where, params

    def query_incidents(self, filters=None, limit=50, offset=0,
                        order_by="detected_at", direction="DESC"):
        filters = filters or {}
        where, params = self._incident_filters(filters)
        allowed = {
            "detected_at", "date", "timestamp", "confidence",
            "incident_id", "camera_id", "location", "status",
        }
        column = order_by if order_by in allowed else "detected_at"
        arrow = "ASC" if str(direction).upper() == "ASC" else "DESC"
        sql = (
            f"SELECT * FROM violations{where} "
            f"ORDER BY {column} {arrow}, incident_id {arrow} LIMIT ? OFFSET ?"
        )
        return self._fetch_dicts(sql, tuple(params) + (int(limit), int(offset)))

    def count_incidents(self, filters=None):
        where, params = self._incident_filters(filters or {})
        rows = self.execute_query(f"SELECT COUNT(*) FROM violations{where}", tuple(params))
        return rows[0][0] if rows else 0

    def review_incident(self, incident_id, status, reviewed_by="", remarks=None):
        sets = ["status = ?", "reviewed_at = ?", "reviewed_by = ?"]
        params = [status, datetime.now().isoformat(timespec="seconds"), reviewed_by]
        if remarks is not None:
            sets.append("remarks = ?")
            params.append(remarks)
        params.append(incident_id)
        return self.execute(
            f"UPDATE violations SET {', '.join(sets)} WHERE incident_id = ?", tuple(params)
        )

    def incident_totals(self, filters=None):
        """Aggregate incident counts and detection/incident ratio in one pass."""
        where, params = self._incident_filters(filters or {})
        rows = self._fetch_dicts(
            f"""
            SELECT COUNT(*) AS incidents,
                   COALESCE(SUM(scene_persons), 0) AS person_frames,
                   COALESCE(SUM(scene_helmet), 0) AS with_helmet,
                   COALESCE(SUM(scene_no_helmet), 0) AS without_helmet,
                   COALESCE(AVG(confidence), 0) AS avg_confidence
            FROM violations{where}
            """,
            tuple(params),
        )
        return rows[0] if rows else {}

    def incidents_grouped(self, column, filters=None, limit=20):
        allowed = {"camera_id", "camera_name", "location", "date", "status", "violation_type"}
        if column not in allowed:
            raise ValueError(f"Cannot group incidents by {column!r}")
        where, params = self._incident_filters(filters or {})
        return self._fetch_dicts(
            f"""
            SELECT {column} AS key, COUNT(*) AS count,
                   COALESCE(AVG(confidence), 0) AS avg_confidence
            FROM violations{where}
            GROUP BY {column} ORDER BY count DESC LIMIT ?
            """,
            tuple(params) + (int(limit),),
        )

    def daily_counts(self, date_from, date_to):
        return self._fetch_dicts(
            """
            SELECT date AS key, COUNT(*) AS count
            FROM violations WHERE date >= ? AND date <= ?
            GROUP BY date ORDER BY date ASC
            """,
            (date_from, date_to),
        )

    def hourly_counts(self, date_from, date_to):
        """Violations per hour of the source-video clock (`timestamp` HH:MM:SS)."""
        return self._fetch_dicts(
            """
            SELECT substr(timestamp, 1, 2) AS key, COUNT(*) AS count
            FROM violations
            WHERE date >= ? AND date <= ? AND length(timestamp) >= 2
            GROUP BY key ORDER BY key ASC
            """,
            (date_from, date_to),
        )

    def distinct_values(self, column):
        allowed = {"camera_id", "camera_name", "location", "status", "violation_type", "video_name"}
        if column not in allowed:
            raise ValueError(f"Cannot list distinct {column!r}")
        rows = self.execute_query(
            f"SELECT DISTINCT {column} FROM violations WHERE {column} != '' ORDER BY {column}"
        )
        return [row[0] for row in rows]

    # ------------------------------------------------------------------
    # SUPERVISOR_MASTER
    # ------------------------------------------------------------------
    def upsert_supervisor(self, supervisor):
        self.execute(INSERT_SUPERVISOR_SQL, (
            supervisor["supervisor_id"],
            supervisor.get("supervisor_name", ""),
            supervisor.get("department", ""),
            supervisor.get("email", ""),
            supervisor.get("phone_number", ""),
            supervisor.get("status", "Active"),
        ))
        return supervisor["supervisor_id"]

    def get_supervisor(self, supervisor_id):
        rows = self._fetch_dicts(
            "SELECT * FROM supervisor_master WHERE supervisor_id = ?", (supervisor_id,)
        )
        return rows[0] if rows else None

    def get_all_supervisors(self, status="Active"):
        if status:
            return self._fetch_dicts(
                "SELECT * FROM supervisor_master WHERE status = ?", (status,)
            )
        return self._fetch_dicts("SELECT * FROM supervisor_master")

    def get_supervisor_for_camera(self, camera_id):
        rows = self._fetch_dicts(
            """
            SELECT s.* FROM supervisor_master s
            JOIN camera_master c ON c.supervisor_id = s.supervisor_id
            WHERE c.camera_id = ? AND s.status = 'Active'
            """,
            (camera_id,),
        )
        return rows[0] if rows else None

    # ------------------------------------------------------------------
    # CAMERA_MASTER
    # ------------------------------------------------------------------
    def upsert_camera(self, camera):
        self.execute(INSERT_CAMERA_SQL, (
            camera["camera_id"],
            camera.get("camera_name", ""),
            camera.get("department", ""),
            camera.get("area", ""),
            camera.get("supervisor_id", ""),
            camera.get("status", "Active"),
            camera.get("location", ""),
            camera.get("ip_address", ""),
            camera.get("rtsp_port", 554),
            camera.get("rtsp_channel", ""),
            camera.get("stream_status", "unknown"),
            1 if camera.get("ai_enabled", True) else 0,
            camera.get("target_fps", 0),
            camera.get("last_seen", ""),
        ))
        return camera["camera_id"]

    def update_camera_stream(self, camera_id, stream_status, last_seen=None):
        return self.execute(
            "UPDATE camera_master SET stream_status = ?, last_seen = ? WHERE camera_id = ?",
            (stream_status, last_seen or datetime.now().isoformat(timespec="seconds"), camera_id),
        )

    def set_camera_ai(self, camera_id, enabled):
        return self.execute(
            "UPDATE camera_master SET ai_enabled = ? WHERE camera_id = ?",
            (1 if enabled else 0, camera_id),
        )

    def delete_camera(self, camera_id):
        return self.execute("DELETE FROM camera_master WHERE camera_id = ?", (camera_id,))

    def get_camera(self, camera_id):
        rows = self._fetch_dicts("SELECT * FROM camera_master WHERE camera_id = ?", (camera_id,))
        return rows[0] if rows else None

    def get_all_cameras(self, status="Active"):
        if status:
            return self._fetch_dicts("SELECT * FROM camera_master WHERE status = ?", (status,))
        return self._fetch_dicts("SELECT * FROM camera_master")

    # ------------------------------------------------------------------
    # RULE_MASTER
    # ------------------------------------------------------------------
    def upsert_rule(self, rule):
        self.execute(INSERT_RULE_SQL, (
            rule["rule_id"],
            rule.get("rule_name", ""),
            rule.get("threshold", ""),
            rule.get("threshold_type", ""),
            rule.get("priority", ""),
            rule.get("status", "Active"),
        ))
        return rule["rule_id"]

    def get_rule(self, rule_id):
        rows = self._fetch_dicts("SELECT * FROM rule_master WHERE rule_id = ?", (rule_id,))
        return rows[0] if rows else None

    def get_rule_by_name(self, rule_name, status="Active"):
        rows = self._fetch_dicts(
            "SELECT * FROM rule_master WHERE rule_name = ? AND status = ?",
            (rule_name, status),
        )
        return rows[0] if rows else None

    def get_rules(self, status="Active"):
        if status:
            return self._fetch_dicts("SELECT * FROM rule_master WHERE status = ?", (status,))
        return self._fetch_dicts("SELECT * FROM rule_master")

    # ------------------------------------------------------------------
    # VIOLATION_HISTORY
    # ------------------------------------------------------------------
    def record_violation(self, record):
        violation_id = self._next_id("violation_history", "VIOL", "violation_id")
        self.execute(INSERT_VIOLATION_HISTORY_SQL, (
            violation_id,
            record.get("track_id", 0),
            record.get("camera_id", ""),
            record.get("supervisor_id", ""),
            record.get("rule_id", ""),
            record.get("violation_type", "Helmet Missing"),
            record.get("date", datetime.now().strftime("%Y-%m-%d")),
            record.get("time", datetime.now().strftime("%H:%M:%S")),
            record.get("duration", ""),
            record.get("screenshot_path", ""),
            record.get("status", "Open"),
            record.get("remarks", ""),
        ))
        return violation_id

    def update_violation_status(self, violation_id, status, remarks=None):
        if remarks is not None:
            return self.execute(
                "UPDATE violation_history SET status = ?, remarks = ? WHERE violation_id = ?",
                (status, remarks, violation_id),
            )
        return self.execute(
            "UPDATE violation_history SET status = ? WHERE violation_id = ?",
            (status, violation_id),
        )

    def get_violations(self, camera_id=None, date=None):
        sql = "SELECT * FROM violation_history"
        params = []
        conditions = []
        if camera_id:
            conditions.append("camera_id = ?")
            params.append(camera_id)
        if date:
            conditions.append("date = ?")
            params.append(date)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY date DESC, time DESC"
        return self._fetch_dicts(sql, tuple(params))

    # ------------------------------------------------------------------
    # ANALYSIS_RUNS
    # ------------------------------------------------------------------
    def save_analysis_run(self, record):
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO analysis_runs
                (run_id, video_name, source_type, camera_id, camera_name, location,
                 started_at, finished_at, date, total_frames, frames_analyzed,
                 people_detected, person_frames, compliant_frames, raw_detections,
                 unique_incidents, elapsed_seconds, processing_fps, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["run_id"],
                    record.get("video_name", ""),
                    record.get("source_type", "recording"),
                    record.get("camera_id", ""),
                    record.get("camera_name", ""),
                    record.get("location", ""),
                    record.get("started_at", ""),
                    record.get("finished_at", ""),
                    record.get("date", datetime.now().strftime("%Y-%m-%d")),
                    record.get("total_frames", 0),
                    record.get("frames_analyzed", 0),
                    record.get("people_detected", 0),
                    record.get("person_frames", 0),
                    record.get("compliant_frames", 0),
                    record.get("raw_detections", 0),
                    record.get("unique_incidents", 0),
                    record.get("elapsed_seconds", 0.0),
                    record.get("processing_fps", 0.0),
                    record.get("status", "completed"),
                ),
            )
        return record["run_id"]

    def analysis_totals(self, date_from=None, date_to=None):
        """Denominators for compliance: how many distinct people were tracked
        and how many of them ended up with a confirmed violation."""
        clauses, params = ["status = 'completed'"], []
        if date_from:
            clauses.append("date >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("date <= ?")
            params.append(date_to)
        where = " WHERE " + " AND ".join(clauses)
        rows = self._fetch_dicts(
            f"""
            SELECT COUNT(*) AS runs,
                   COALESCE(SUM(people_detected), 0) AS people_detected,
                   COALESCE(SUM(person_frames), 0) AS person_frames,
                   COALESCE(SUM(compliant_frames), 0) AS compliant_frames,
                   COALESCE(SUM(raw_detections), 0) AS raw_detections,
                   COALESCE(SUM(unique_incidents), 0) AS unique_incidents,
                   COALESCE(SUM(frames_analyzed), 0) AS frames_analyzed
            FROM analysis_runs{where}
            """,
            tuple(params),
        )
        return rows[0] if rows else {}

    def get_analysis_runs(self, limit=25):
        return self._fetch_dicts(
            "SELECT * FROM analysis_runs ORDER BY finished_at DESC LIMIT ?", (int(limit),)
        )

    # ------------------------------------------------------------------
    # EMAIL_LOG
    # ------------------------------------------------------------------
    def log_email(self, record):
        email_log_id = self._next_id("email_log", "EML", "email_log_id")
        self.execute(INSERT_EMAIL_LOG_SQL, (
            email_log_id,
            record.get("violation_id", ""),
            record.get("supervisor_id", ""),
            record.get("email_address", ""),
            record.get("sent_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            record.get("delivery_status", "SENT"),
            record.get("retry_count", 0),
            record.get("remarks", ""),
        ))
        return email_log_id

    def get_email_logs(self, violation_id=None):
        sql = "SELECT * FROM email_log"
        params = []
        if violation_id:
            sql += " WHERE violation_id = ?"
            params.append(violation_id)
        sql += " ORDER BY sent_time DESC"
        return self._fetch_dicts(sql, tuple(params))
