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

MIGRATIONS = [
    ("scene_persons", "INTEGER DEFAULT 0"),
    ("scene_helmet", "INTEGER DEFAULT 0"),
    ("scene_no_helmet", "INTEGER DEFAULT 0"),
    ("poster_path", "TEXT DEFAULT ''"),
]

INSERT_VIOLATION_SQL = """
INSERT OR REPLACE INTO violations
(incident_id, camera_name, camera_id, location, video_name,
 image_path, poster_path, timestamp, date, violation_type, confidence,
 track_id, scene_persons, scene_helmet, scene_no_helmet, status)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

INSERT_SUPERVISOR_SQL = """
INSERT OR REPLACE INTO supervisor_master
(supervisor_id, supervisor_name, department, email, phone_number, status)
VALUES (?, ?, ?, ?, ?, ?)
"""

INSERT_CAMERA_SQL = """
INSERT OR REPLACE INTO camera_master
(camera_id, camera_name, department, area, supervisor_id, status)
VALUES (?, ?, ?, ?, ?, ?)
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
        existing = {row[1] for row in cursor.execute("PRAGMA table_info(violations)").fetchall()}
        for column, definition in MIGRATIONS:
            if column not in existing:
                cursor.execute(f"ALTER TABLE violations ADD COLUMN {column} {definition}")
                logger.info(f"Database migrated: added column {column}")

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
            ))
        return record["incident_id"]

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
        ))
        return camera["camera_id"]

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
