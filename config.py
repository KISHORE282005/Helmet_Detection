import os
import sys
import logging
from pathlib import Path

BASE_DIR = Path(__file__).parent


def _load_dotenv():
    """Parse a simple KEY=VALUE .env file (no external dependencies).

    Values are returned as raw strings; quotes are stripped. Lines starting
    with '#' and empty lines are ignored. Secrets are also exported to
    os.environ so they stay available to any subprocess.
    """
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return {}
    values = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    for key, value in values.items():
        os.environ.setdefault(key, value)
    return values


def _apply_env_overrides(env):
    """Override any existing module setting whose key is present in .env.

    The value is coerced to the type of the current default so booleans,
    integers and floats keep their semantics. Complex settings (tuples /
    lists such as color ranges) are skipped with a warning.
    """
    module = sys.modules[__name__]
    for key, raw in env.items():
        if not key.isupper() or not hasattr(module, key):
            logging.getLogger(__name__).warning(f"Unknown .env key ignored: {key}")
            continue
        current = getattr(module, key)
        try:
            if isinstance(current, bool):
                setattr(module, key, raw.lower() in ("1", "true", "yes", "on"))
            elif isinstance(current, int):
                setattr(module, key, int(raw))
            elif isinstance(current, float):
                setattr(module, key, float(raw))
            elif isinstance(current, (list, tuple)):
                logging.getLogger(__name__).warning(
                    f".env key {key} is a complex setting and was ignored"
                )
                continue
            else:
                setattr(module, key, str(raw))
        except (TypeError, ValueError) as exc:
            logging.getLogger(__name__).warning(f".env key {key} rejected ({raw!r}): {exc}")


_ENV = _load_dotenv()

MODELS_DIR = BASE_DIR / "models"
VIDEOS_DIR = BASE_DIR / "videos"
OUTPUT_DIR = BASE_DIR / "output"
IMAGES_DIR = OUTPUT_DIR / "images"
REPORTS_DIR = OUTPUT_DIR / "reports"
LOGS_DIR = OUTPUT_DIR / "logs"
DATABASE_DIR = BASE_DIR / "database"
WARNING_POSTERS_DIR = OUTPUT_DIR / "posters"
EMAIL_TEMP_DIR = OUTPUT_DIR / "temp"

for dir_path in [MODELS_DIR, VIDEOS_DIR, OUTPUT_DIR, IMAGES_DIR, REPORTS_DIR, LOGS_DIR, DATABASE_DIR, WARNING_POSTERS_DIR, EMAIL_TEMP_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

PERSON_MODEL_PATH = MODELS_DIR / "yolo11x.pt"
HELMET_MODEL_PATH = MODELS_DIR / "helmet.pt"

CONFIDENCE_THRESHOLD = 0.60
PERSON_CLASS_ID = 0
# Analyze the FULL video: every single frame is checked so no violation is missed.
# Set higher (e.g. 3) only if you need speed at the cost of coverage.
FRAME_SKIP = 1
RESIZE_WIDTH = 1280
# Minimum helmet-color coverage of the CROWN region (non-skin pixels) before
# a head is accepted as wearing a helmet. Raised so that skin, hair and
# background can never reach it (a real helmet crown is mostly helmet color).
HELMET_MIN_RATIO = 0.45
MAX_TRACK_AGE = 60
IMAGE_QUALITY = 95

# ---------------------------------------------------------------------------
# Temporal verification (false-positive reduction)
# ---------------------------------------------------------------------------
# A violation is NEVER generated from a single frame. Each tracked person is
# monitored over time and confirmed only after "No Helmet" is detected for
# VIOLATION_REQUIRED_FRAMES CONSECUTIVE valid frames. If the prediction flips
# back to Helmet, the counter resets. (Counter counts analyzed frames; at
# FRAME_SKIP=1 that equals raw frames, e.g. 30 frames ~ 1.5-2s at 20-25fps.)
VIOLATION_REQUIRED_FRAMES = 30
# Minimum decision confidence for a helmet classification to count as a valid
# frame. Lower-confidence frames are ignored (continue monitoring).
HELMET_CONFIDENCE_THRESHOLD = 0.90
# If a track disappears for more than this many analyzed frames, its
# consecutive counter resets on the next sighting (temporal continuity broken).
CONSECUTIVE_GAP_RESET = 5
# When multiple people are confirmed without helmets within this many frames,
# they share ONE evidence image + poster (single capture for multiple users).
GROUP_WINDOW_FRAMES = 15
# Per-track helmet-status history kept for diagnostics.
TRACK_HISTORY_SIZE = 60

# ---------------------------------------------------------------------------
# Head-region validation (ignore unreliable frames)
# ---------------------------------------------------------------------------
MIN_HEAD_SIZE = 30              # min head-ROI dimension in px (too small = unreliable)
MIN_HEAD_SHARPNESS = 30.0       # Laplacian variance (motion blur / out of focus)
MIN_HEAD_BRIGHTNESS = 30.0      # mean V of head ROI (too dark)
MAX_HEAD_BRIGHTNESS = 250.0     # mean V of head ROI (overexposed)
MIN_HEAD_CONTRAST = 15.0        # std of V of head ROI (severe occlusion / flat)
MAX_HEAD_EDGE_OVERLAP = 0.15    # fraction of head bbox cropped by frame edge

# Warning poster output
WARNING_POSTERS_DIR = OUTPUT_DIR / "posters"

# ---------------------------------------------------------------------------
# Notification module (supervisor alerting)
# ---------------------------------------------------------------------------
DB_SEED_DEFAULTS = True                   # seed SUPERVISOR/CAMERA/RULE master data if empty
RULE_OVERRIDE_ENABLED = True              # apply numeric thresholds from RULE_MASTER to config

# SMTP / email settings. Leave EMAIL_SMTP_USERNAME/PASSWORD empty for
# unauthenticated SMTP servers (e.g. local relay). Set EMAIL_ENABLED = False
# to run the system without sending any mail (status stored as SKIPPED).
EMAIL_ENABLED = True
EMAIL_SMTP_HOST = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587
EMAIL_SMTP_USE_TLS = True
EMAIL_SMTP_USERNAME = ""
EMAIL_SMTP_PASSWORD = ""
EMAIL_FROM = "aisafety@example.com"
EMAIL_SUBJECT = "\U0001F6A8 AI Safety Violation Alert"
EMAIL_MAX_RETRIES = 1                    # retries AFTER the first attempt (total = 2)
EMAIL_TIMEOUT = 30                       # SMTP socket timeout in seconds
EMAIL_IMAGE_QUALITY = 95                 # JPEG quality of attached screenshots

# If a camera is missing from CAMERA_MASTER, fall back to this supervisor.
# Leave empty to skip notification (violation still recorded) when unmapped.
DEFAULT_SUPERVISOR_ID = ""

# If 2+ people are without helmets in the same frame, capture ONE evidence
# image showing all of them together (in addition to single-person captures).
GROUP_CAPTURE_ENABLED = True

DEFAULT_CAMERA_NAME = "Assembly Line 01"
DEFAULT_CAMERA_ID = "CAM001"
DEFAULT_LOCATION = "Production Area A"

# ---------------------------------------------------------------------------
# Filename-based camera info (fallback when the video has no embedded metadata)
# ---------------------------------------------------------------------------
# Camera name / ID / location are derived from the uploaded video's filename
# (e.g. "CAM01_ProductionArea_shiftA.mp4"). Embedded video metadata always
# takes priority; the filename fills any missing field.
FILENAME_PARSING_ENABLED = True
CAMERA_PREFIXES = (
    "cam", "camera", "ch", "channel", "ip", "ipc", "dvr", "nvr", "cctv",
)
LOCATION_KEYWORDS = (
    "area", "plant", "line", "zone", "floor", "building", "gate", "dock",
    "entrance", "exit", "hall", "sector", "warehouse", "production",
    "assembly", "loading", "parking", "section", "bay", "yard", "room",
    "block", "storage", "workshop", "lot", "office", "unit", "level", "site",
    "campus", "factory", "stage", "station",
    "north", "south", "east", "west", "main", "rear", "front", "side",
    "upper", "lower", "middle", "back", "central",
)
NOISE_TOKENS = (
    "rec", "record", "recording", "video", "clip", "sample", "test",
    "final", "new", "copy", "export", "output", "tmp", "h264", "h265",
    "mpeg", "full", "raw",
)

# Safety-helmet color ranges (HSV, OpenCV H in 0-180). Ranges are kept
# deliberately NARROW so skin tones, hair and shadows can never match:
# - orange/white are the two families that skin most resembles; orange needs
#   high saturation (S>=150), white needs very high brightness (V>=215).
# - skin pixels are additionally masked out before matching (see detector).
HELMET_COLOR_RANGES = [
    ("yellow", [20, 110, 110], [35, 255, 255]),
    ("white", [0, 0, 200], [180, 20, 255]),
    ("blue", [100, 90, 60], [130, 255, 255]),
    ("orange", [5, 150, 120], [18, 255, 255]),
    ("green", [40, 90, 60], [90, 255, 255]),
    ("red", [0, 150, 90], [8, 255, 255]),
    ("dark-red", [168, 110, 60], [180, 255, 210]),
]

# HSV ranges (OpenCV H in 0-180) of typical human skin. Pixels matching skin
# are EXCLUDED from helmet matching so a bare head is never read as a helmet.
SKIN_COLOR_RANGES = [
    ([0, 40, 40], [22, 175, 255]),   # light / tan / warm skin
    ([0, 25, 20], [22, 175, 80]),    # darker skin tones
]

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Apply .env overrides last so any setting above can be changed via .env.
_apply_env_overrides(_ENV)
