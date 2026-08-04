import logging

logger = logging.getLogger(__name__)

DEFAULT_SUPERVISORS = [
    {
        "supervisor_id": "SUP001",
        "supervisor_name": "Mr. Kumar",
        "department": "Assembly",
        "email": "kumar.demo@gmail.com",
        "phone_number": "9876543210",
        "status": "Active",
    },
    {
        "supervisor_id": "SUP002",
        "supervisor_name": "Ms. Priya",
        "department": "Paint",
        "email": "priya.demo@gmail.com",
        "phone_number": "9876543211",
        "status": "Active",
    },
]

DEFAULT_CAMERAS = [
    {
        "camera_id": "CAM001",
        "camera_name": "Assembly Line 1",
        "department": "Assembly",
        "area": "Stage 1",
        "supervisor_id": "SUP001",
        "status": "Active",
    },
    {
        "camera_id": "CAM002",
        "camera_name": "Assembly Line 2",
        "department": "Assembly",
        "area": "Stage 2",
        "supervisor_id": "SUP001",
        "status": "Active",
    },
    {
        "camera_id": "CAM003",
        "camera_name": "Paint Booth",
        "department": "Paint",
        "area": "Booth 1",
        "supervisor_id": "SUP002",
        "status": "Active",
    },
]

DEFAULT_RULES = [
    {
        "rule_id": "R001",
        "rule_name": "Helmet Missing",
        "threshold": "Immediate",
        "threshold_type": "Seconds",
        "priority": "High",
        "status": "Active",
    }
]


def seed_master_data(db):
    """Insert default master data only when the tables are empty."""
    if not db.get_all_supervisors(status=None):
        for supervisor in DEFAULT_SUPERVISORS:
            db.upsert_supervisor(supervisor)
        logger.info(f"Seeded {len(DEFAULT_SUPERVISORS)} supervisors")
    else:
        logger.info("supervisor_master already populated; skipping seed")

    if not db.get_all_cameras(status=None):
        for camera in DEFAULT_CAMERAS:
            db.upsert_camera(camera)
        logger.info(f"Seeded {len(DEFAULT_CAMERAS)} cameras")
    else:
        logger.info("camera_master already populated; skipping seed")

    if not db.get_rules(status=None):
        for rule in DEFAULT_RULES:
            db.upsert_rule(rule)
        logger.info(f"Seeded {len(DEFAULT_RULES)} rules")
    else:
        logger.info("rule_master already populated; skipping seed")
