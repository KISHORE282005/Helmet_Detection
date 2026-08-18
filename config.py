import os
import re
import sys
import logging
from pathlib import Path
from urllib.parse import quote

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
        # A blank value, or a literal "None"/"null", means "leave the default
        # alone". Without this, DEFAULT_CAMERA_NAME=None would set the *string*
        # "None" — which is truthy, so incidents would be filed against a camera
        # literally named None.
        if raw.strip().lower() in ("", "none", "null") and not isinstance(current, bool):
            continue
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

DEFAULT_CAMERA_NAME = "None"
DEFAULT_CAMERA_ID = "None"
DEFAULT_LOCATION = "None"

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

# ---------------------------------------------------------------------------
# NVA (Non-Value-Added) activity analysis
# ---------------------------------------------------------------------------
# Classifies what each tracked person is doing from their trajectory, charges
# that time to Value-Added / Necessary-NVA / NVA, and recommends the lean
# countermeasure for the biggest waste. Runs on the tracks the safety pipeline
# already produces, so it costs no extra inference.
#
# All distance thresholds are in BODY-HEIGHTS (the person's own bounding-box
# height), never pixels — that is what makes one setting correct for someone
# standing next to the camera and someone at the far end of the bay.
NVA_ENABLED = True
# Rolling trajectory window each decision is made over. Shorter reacts faster
# and reads noisier; longer is calmer but blurs short activities together.
NVA_WINDOW_SECONDS = 4.0
# The window is averaged into waypoints this far apart before distances are
# measured. This is what stops bounding-box jitter accumulating into a
# walking speed for a person who never moved.
NVA_SAMPLE_SECONDS = 0.5
# A label must win a majority of this much history before it can open a
# segment, so one occluded frame cannot invent an activity.
NVA_SMOOTHING_SECONDS = 1.5
# Below this speed (body-heights/second) a person counts as stationary.
NVA_IDLE_SPEED = 0.08
# At or above this speed they are travelling rather than working in place.
NVA_WALK_SPEED = 0.35
# ...or when they end up this far from where the window started.
NVA_TRAVEL_NET = 1.20
# Travel whose net displacement is below this fraction of the distance walked
# is wandering, not going somewhere: searching rather than walking.
NVA_SEARCH_STRAIGHTNESS = 0.50
# Repeated back-and-forth trips. This is a longer-horizon pattern than the
# others — whether a single round trip falls inside a 4-second window is a
# matter of timing — so it is judged over its own, longer history. A shuttle
# must reverse direction this many times, cover this much ground doing it, and
# end up near where it started: all three, so someone who turns around once on
# a normal walk is never recorded as waste.
NVA_SHUTTLE_WINDOW_SECONDS = 12.0
NVA_SHUTTLE_REVERSALS = 3
NVA_SHUTTLE_MIN_PATH = 4.0
NVA_SHUTTLE_STRAIGHTNESS = 0.35
# Smallest movement (body-heights) that counts as a direction rather than noise.
NVA_REVERSAL_MIN_STEP = 0.25
# Stationary people within this many body-heights of each other are a group
# huddle rather than separate idle individuals (~2.6 m for a 1.75 m person).
NVA_GROUP_PROXIMITY = 1.5
NVA_GROUP_MIN_PEOPLE = 2
# Shortest run of an activity worth recording. A brief pause is work rhythm,
# not waiting, so short runs are never charged to waste.
NVA_MIN_SEGMENT_SECONDS = 3.0
NVA_IDLE_MIN_SECONDS = 8.0
# A track needs this much history before it is classified at all.
NVA_MIN_TRACK_SECONDS = 2.0
# A person out of view longer than this breaks trajectory continuity: the open
# segment is closed rather than bridged across the gap.
NVA_GAP_RESET_SECONDS = 3.0

# Recommendation engine. An activity below the minimum share produces no
# recommendation — a handful of stray seconds must never become a work order.
NVA_RECOMMEND_MIN_SHARE = 2.0
NVA_SEVERITY_MEDIUM_SHARE = 7.0
NVA_SEVERITY_HIGH_SHARE = 15.0
# Walking is necessary, so it is only raised once it is disproportionate.
NVA_WALKING_ALERT_SHARE = 20.0
# Value-added ratio the line is being held to, in percent.
NVA_TARGET_VA_RATIO = 60.0

# ---------------------------------------------------------------------------
# SafeVision AI API server
# ---------------------------------------------------------------------------
# Bind address for `python -m api`. Use 0.0.0.0 to expose the dashboard to
# other machines on the plant network; 127.0.0.1 keeps it local to this host.
API_HOST = "127.0.0.1"
API_PORT = 8000
API_RELOAD = False
# Comma-separated browser origins allowed to call the API. Only needed for the
# Vite dev server; the production build is served by this same process.
API_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
# Largest video accepted by the upload endpoint.
API_MAX_UPLOAD_MB = 2048

# ---------------------------------------------------------------------------
# Camera network / RTSP
# ---------------------------------------------------------------------------
# How often the dashboard re-checks whether each camera answers on its RTSP
# port, and how long to wait for that answer.
CAMERA_POLL_INTERVAL = 20.0
CAMERA_CONNECT_TIMEOUT = 1.5

# RTSP credentials. These stay on the server: they are never written to the
# database, never returned by the API, and never reach the browser. Leave the
# username blank for cameras that allow anonymous streaming.
RTSP_USERNAME = ""
RTSP_PASSWORD = ""
RTSP_DEFAULT_PORT = 554
# Hikvision stream path. {channel} is replaced with the camera's channel value
# (101 = channel 1 main stream, 102 = channel 1 sub stream).
RTSP_STREAM_PATH = "/Streaming/Channels/{channel}"
RTSP_DEFAULT_CHANNEL = "101"

# FFmpeg transport for the stream. TCP is strongly preferred on Hikvision:
# over UDP a busy plant network drops packets and the decoder hands back torn
# frames, which the detector then scores as real content.
RTSP_TRANSPORT = "tcp"
# How long to wait for the camera to answer the initial handshake, and for any
# later read, before treating the link as dead. Without these OpenCV waits a
# fixed 30s, so an unreachable camera blocks a snapshot request for half a
# minute before reporting the obvious.
RTSP_OPEN_TIMEOUT_MS = 8000
RTSP_READ_TIMEOUT_MS = 8000
# Frames the capture may queue. Live analysis wants the newest frame, not a
# backlog: a deeper buffer makes the pipeline report violations that are
# already several seconds old.
RTSP_BUFFER_SIZE = 1
# A live stream that stops delivering frames is usually a network blip, not
# the end of the footage, so reopen it this many times before ending the run.
# 0 disables reconnection.
RTSP_RECONNECT_ATTEMPTS = 5
RTSP_RECONNECT_DELAY = 3.0
# Used when the camera reports no frame rate. Timestamps on incidents are
# derived from FPS, so this must never be left at zero.
RTSP_FALLBACK_FPS = 15.0

# ---------------------------------------------------------------------------
# Live analysis
# ---------------------------------------------------------------------------
# Stop a live session automatically after this many seconds. 0 = run until the
# operator stops it.
LIVE_MAX_DURATION_SECONDS = 0
# Live sessions allowed to run at once. Each one loads its own copy of the
# detection models, so raising this costs both memory and throughput.
LIVE_MAX_SESSIONS = 1

# ---------------------------------------------------------------------------
# Primary camera provisioning
# ---------------------------------------------------------------------------
# Set CAMERA_IP in .env to register your camera automatically on startup. The
# record is created if missing and its address is kept in step on every boot,
# so a camera can be brought online by editing one line. Leave CAMERA_IP blank
# to manage cameras entirely from the dashboard instead.
CAMERA_IP = ""
CAMERA_ID = "CAM001"
CAMERA_NAME = "Assembly Line 1"
CAMERA_LOCATION = "Production Area A"
CAMERA_DEPARTMENT = "Assembly"
CAMERA_CHANNEL = "101"
CAMERA_TARGET_FPS = 10
CAMERA_SUPERVISOR_ID = ""

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def rtsp_url(ip_address, port=None, channel=None, username=None, password=None):
    """Build the full RTSP URL for a camera. SERVER-SIDE ONLY.

    The result embeds credentials, so it must never be returned by the API,
    logged, or sent to the browser — pass it through `redact_rtsp_url` first.
    Use it only to open a stream.
    """
    if not ip_address:
        return None

    ip_address = str(ip_address).strip()
    # An operator may paste a complete URL into the address field. Honour it
    # verbatim so cameras with a non-Hikvision path still work.
    if "://" in ip_address:
        return ip_address

    user = RTSP_USERNAME if username is None else username
    secret = RTSP_PASSWORD if password is None else password

    credentials = ""
    if user:
        # Camera passwords routinely contain @ : / #. Unquoted, those are
        # parsed as URL structure and authentication fails with a misleading
        # "could not open stream" rather than a 401.
        credentials = quote(str(user), safe="")
        if secret:
            credentials += ":" + quote(str(secret), safe="")
        credentials += "@"

    path = RTSP_STREAM_PATH.format(channel=str(channel or RTSP_DEFAULT_CHANNEL))
    if path and not path.startswith("/"):
        path = "/" + path
    return f"rtsp://{credentials}{ip_address}:{int(port or RTSP_DEFAULT_PORT)}{path}"


def rtsp_url_for_camera(camera):
    """Build the stream URL from a camera_master row. SERVER-SIDE ONLY.

    Credentials come from .env rather than the row, because the database
    deliberately never stores them.
    """
    if not camera:
        return None
    return rtsp_url(
        camera.get("ip_address"),
        port=camera.get("rtsp_port"),
        channel=camera.get("rtsp_channel"),
    )


# Matches the credential segment of any URL: scheme, then everything up to the
# '@' that precedes the host. Anchoring on the scheme means a stray '@' later
# in a sentence or query string is left alone.
_URL_CREDENTIALS = re.compile(r"(?P<scheme>[a-zA-Z][\w+.\-]*://)[^/\s@]*@")


def redact_rtsp_url(text):
    """Replace embedded URL credentials with `***`.

    Accepts a bare URL or any string containing one, because exception
    messages from OpenCV routinely quote back the URL they were handed. Every
    log line, error message and API response that mentions a stream must go
    through this — an unredacted RTSP URL is a password in plain text.
    """
    if not text:
        return ""
    return _URL_CREDENTIALS.sub(lambda m: f"{m.group('scheme')}***@", str(text))

# Apply .env overrides last so any setting above can be changed via .env.
_apply_env_overrides(_ENV)
