import os
import logging
from pathlib import Path

BASE_DIR = Path(__file__).parent

MODELS_DIR = BASE_DIR / "models"
VIDEOS_DIR = BASE_DIR / "videos"
OUTPUT_DIR = BASE_DIR / "output"
IMAGES_DIR = OUTPUT_DIR / "images"
REPORTS_DIR = OUTPUT_DIR / "reports"
LOGS_DIR = OUTPUT_DIR / "logs"
DATABASE_DIR = BASE_DIR / "database"

for dir_path in [MODELS_DIR, VIDEOS_DIR, OUTPUT_DIR, IMAGES_DIR, REPORTS_DIR, LOGS_DIR, DATABASE_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

PERSON_MODEL_PATH = MODELS_DIR / "yolo11n.pt"
HELMET_MODEL_PATH = MODELS_DIR / "helmet.pt"

CONFIDENCE_THRESHOLD = 0.60
PERSON_CLASS_ID = 0
HELMET_CLASS_IDS = [1]
FRAME_SKIP = 3
RESIZE_WIDTH = 1280
MAX_TRACK_AGE = 60
MAX_FRAMES_VISIBLE = 500
SAVE_VIOLATION_IMAGES = True
IMAGE_QUALITY = 95
REPORT_TYPE = "excel"

DEFAULT_CAMERA_NAME = "Assembly Line 01"
DEFAULT_CAMERA_ID = "CAM001"
DEFAULT_LOCATION = "Production Area A"

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
