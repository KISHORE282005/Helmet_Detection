# SafeVision AI — Industrial PPE Safety Monitoring

**AI-Based Helmet Detection and Automated Safety Violation Reporting System**

A Proof-of-Concept system that analyzes CCTV footage to detect workers without safety helmets, captures evidence images, and generates automated violation reports.

It ships in two parts:

- **The detection pipeline** — YOLO11 + ByteTrack, driven from the CLI, the tkinter GUI, or the API.
- **SafeVision AI** — a web operations dashboard (FastAPI + React) for supervisors: live camera state, the violation review queue, evidence, reports and analytics.

## System Architecture

```
CCTV Video → Frame Extraction → YOLO Person Detection → Helmet Check
                                                              │
                                                   ┌──────────┴──────────┐
                                                   │                    │
                                               Has Helmet         No Helmet
                                                   │                    │
                                    ┌──────────────┘        Head-Region Validation
                                    │                 (size / focus / light / crop)
                                    │                            │
                                    │                 Temporal Verification (per track)
                                    │                            │
                                    │                  No Helmet for 30 consecutive
                                    │                  valid frames (counter resets on
                                    │                  helmet / low confidence / gap)
                                    │                            │
                                    │                 Confirm → Evidence Image + Poster
                                    │                            │
                                    │                 Record Incident → Excel + SQLite
```

## Requirements

- Python 3.10+
- Windows / Linux / macOS

### Dependencies

```
ultralytics>=8.3.0     YOLOv11 object detection
opencv-python>=4.9.0   Video processing
numpy>=1.24.0          Data handling
pandas>=2.0.0          Report dataframes
openpyxl>=3.1.0        Excel export
boxmot>=10.0.0         ByteTrack multi-object tracking
Pillow>=10.0.0         Image handling
```

## Quick Start

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Place CCTV video in videos/
#    Supported: .mp4 .avi .mov .mkv .webm

# 3a. GUI mode (recommended)
python gui.py

# 3b. Interactive CLI mode
python app.py -i

# 3c. Direct mode
python app.py videos/Shift_A.mp4
```

## SafeVision AI Dashboard

The web dashboard is the supervisor-facing interface. It runs on the same
database and output folders as the CLI, so anything analyzed from the terminal
shows up in the dashboard immediately.

### Run it

```powershell
# One-time: build the front end
cd frontend
npm install
npm run build
cd ..

# Start the server — serves both the API and the built dashboard
python -m api
```

Open **http://127.0.0.1:8000**.

For front-end development, run the API and the Vite dev server side by side:

```powershell
python -m api --reload          # terminal 1  → http://127.0.0.1:8000
cd frontend && npm run dev      # terminal 2  → http://localhost:5173
```

Interactive API documentation is at `http://127.0.0.1:8000/docs`.

### What the dashboard does

| Page | Purpose |
|---|---|
| **Dashboard** | Cameras online, open violations, today vs yesterday, compliance rate, camera wall, 7-day trend, review queue, system health |
| **Live Cameras / Camera Grid** | Per-camera connection state and the most recent AI evidence; 4 columns on desktop, 2 on laptop, 1 on tablet |
| **Video Analysis** | Upload recorded CCTV footage and watch the real pipeline counters — frames, people tracked, raw detections, unique incidents, processing FPS |
| **Active Violations** | The supervisor work queue: every incident awaiting a decision |
| **Incident History** | Searchable, filterable table (camera, location, status, date range, confidence) with paging |
| **Incident Review** | Evidence frame and warning poster, full incident facts, the detection→violation→incident→evidence chain, and Confirm / False Positive / Resolved actions |
| **Evidence Gallery** | Visual triage across incidents with a detail modal |
| **Reports** | Daily / weekly / monthly summaries, exportable to Excel, PDF and CSV |
| **Analytics** | Violation trend, violations per camera and per location, hour-of-day distribution, duplicate-suppression ratio, recent runs |
| **Cameras** | Camera registry, location and supervisor mapping, AI enable/disable, connection test |
| **AI Models** | Model inventory, engine state, and the Phase 2 recognition roadmap |
| **Settings** | Detection, tracking and incident thresholds, applied to the next analysis run |

### Detection vs violation vs incident

The dashboard keeps these separate everywhere, because the difference is the
whole point of the tracker:

| Term | Meaning |
|---|---|
| **Detection** | A person found in one analyzed frame |
| **Violation** | A tracked person reading as helmet-missing |
| **Incident** | **One** record per tracked person, after temporal confirmation |
| **Evidence** | The best frame of that confirmed run |

One worker without a helmet across 500 frames produces **one incident**, not 500.
The Video Analysis and Analytics pages report raw detections and unique
incidents side by side so the suppression is visible rather than assumed.

### Reported numbers are real

Nothing on the dashboard is simulated. Where the backend has no data, the UI
shows an em dash and says why — an empty system has no compliance rate, and
showing 100% would be false. Specifically:

- **Cameras online** counts cameras whose RTSP port accepted a TCP connection.
  Phase 1 does not decode the stream, and the UI says so rather than implying
  live video.
- **Compliance rate** is tracked people minus confirmed violators, over tracked
  people, from completed analysis runs. It is `—` until footage is analyzed.
- **Analysis progress** comes from the running pipeline via a progress callback.

### Security

- RTSP usernames and passwords are never stored, transmitted to the browser, or
  displayed. Cameras expose only an IP, a port, and a connection state.
- Evidence, poster and report files are served through `/api/media/{kind}/{name}`,
  which resolves paths inside a fixed allow-list of output directories and
  rejects anything that escapes them.
- Absolute server filesystem paths are stripped from API responses.
- SMTP credentials live in `.env` and are never exposed by the API.

## GUI Usage

1. Click **Upload Video** — select a CCTV video file
2. (Optional) Edit Camera Name / ID / Location (auto-filled from the video's embedded metadata when present)
3. Click **Start Processing**
4. View live log output; summary popup appears on completion

When a video is uploaded, the Camera Name, Camera ID, and Location fields are automatically
populated from the **video filename** (e.g. `CAM01_ProductionArea_shiftA.mp4` → ID `CAM01`,
name `shiftA`, location `ProductionArea`). Embedded video metadata (MP4/MOV QuickTime atoms,
AVI INFO chunks, MKV tags) is used first when present; the filename fills any missing field.
If neither yields a value, the defaults from `config.py` are used. Tune parsing via
`FILENAME_PARSING_ENABLED`, `CAMERA_PREFIXES`, `LOCATION_KEYWORDS`, and `NOISE_TOKENS`.

## CLI Usage

```
usage: app.py [-h] [--camera-name CAMERA_NAME] [--camera-id CAMERA_ID]
              [--location LOCATION] [--list-videos] [--conf CONF]
              [--interactive] [video]

positional arguments:
  video                 Path to CCTV video file

options:
  -h, --help            Show this help
  --camera-name NAME    Camera name (default: from video metadata, else Assembly Line 01)
  --camera-id ID        Camera ID (default: from video metadata, else CAM001)
  --location LOC        Location (default: from video metadata, else Production Area A)
  --list-videos         List videos in ./videos/
  --conf CONF           Confidence threshold 0-1 (default: 0.60)
  --interactive, -i     Interactive video picker
```

## Project Structure

```
Helmet_Detection/
├── app.py               CLI entry point
├── gui.py               GUI entry point (tkinter)
├── config.py            All configuration settings
├── requirements.txt     Python dependencies
├── api/                 FastAPI backend for the dashboard
│   ├── main.py          App factory, CORS, SPA hosting
│   ├── __main__.py      `python -m api`
│   ├── state.py         Shared DB / config / model singletons, media path guard
│   ├── schemas.py       Request bodies and row → API serializers
│   ├── routers/         dashboard, incidents, cameras, analysis,
│   │                    analytics, reports, settings, system, media
│   └── services/        Background analysis jobs, camera reachability polling
├── frontend/            React + TypeScript + Tailwind dashboard
│   ├── src/lib/         API client, hooks, types, formatting
│   ├── src/components/  UI primitives, charts, layout, domain components
│   ├── src/pages/       One file per route
│   └── dist/            Production build (served by FastAPI)
├── models/              YOLO model files (*.pt)
│   └── yolo11n.pt       Pre-trained person detector (auto-downloaded)
├── videos/              Place CCTV videos here
├── output/
│   ├── images/          Violation evidence images (annotated)
│   ├── posters/         Warning posters (banner + annotated frame)
│   ├── reports/         Generated Excel safety reports
│   └── logs/            Processing logs
├── database/
│   └── violations.db    SQLite violation database
├── detector/
│   └── yolo_detector.py YOLOv11 person + helmet detection + head validation
├── tracker/
│   └── tracker.py       ByteTrack multi-object tracking
├── report/
│   └── report_generator.py  Excel + SQLite report generation
└── utils/
    ├── video_utils.py      Video I/O, frame resizing
    ├── image_utils.py      Violation image capture & annotation & posters
    └── violation_tracker.py  Temporal (multi-frame) violation verification
```

## Configuration

Edit `config.py` to adjust:

| Setting | Default | Description |
|---------|---------|-------------|
| `CONFIDENCE_THRESHOLD` | `0.60` | Minimum person-detection confidence |
| `FRAME_SKIP` | `1` | Process every Nth frame (1 = full-video analysis; higher = faster, misses frames) |
| `RESIZE_WIDTH` | `1280` | Resize frame width (preserves aspect ratio) |
| `MAX_TRACK_AGE` | `60` | Max frames to keep lost tracks |
| `VIOLATION_REQUIRED_FRAMES` | `30` | Consecutive no-helmet frames required to confirm a violation (~1.5–2 s at 20–25 fps) |
| `HELMET_CONFIDENCE_THRESHOLD` | `0.90` | Minimum helmet-classification confidence to count a frame (lower = ignored, not reset) |
| `CONSECUTIVE_GAP_RESET` | `5` | Frames a track may disappear before its counter resets |
| `GROUP_WINDOW_FRAMES` | `15` | Confirmed violators within this many frames share ONE evidence image + poster |
| `TRACK_HISTORY_SIZE` | `60` | Per-track helmet-status history kept for diagnostics |
| `MIN_HEAD_SIZE` | `30` | Min head-ROI dimension (px); smaller heads are unreliable |
| `MIN_HEAD_SHARPNESS` | `30.0` | Min Laplacian variance (rejects motion blur / out of focus) |
| `MIN_HEAD_BRIGHTNESS` | `30.0` | Min head brightness (rejects too-dark frames) |
| `MAX_HEAD_BRIGHTNESS` | `250.0` | Max head brightness (rejects overexposure) |
| `MIN_HEAD_CONTRAST` | `15.0` | Min head contrast (rejects occlusion / flat regions) |
| `MAX_HEAD_EDGE_OVERLAP` | `0.15` | Max fraction of the head cropped by the frame edge |
| `GROUP_CAPTURE_ENABLED` | `True` | Capture 2+ no-helmet people in one shared evidence image |
| `DEFAULT_CAMERA_NAME` | `Assembly Line 01` | Default camera label |
| `FILENAME_PARSING_ENABLED` | `True` | Derive camera info from the video filename when no metadata exists |
| `CAMERA_PREFIXES` | `cam, camera, ch, ...` | Tokens that mark a camera ID in the filename |
| `LOCATION_KEYWORDS` | `area, plant, line, ...` | Words that mark a location in the filename |
| `HELMET_MODEL_PATH` | `models/helmet.pt` | Custom helmet model (optional) |

## Helmet Detection

The system uses two methods (in priority order):

1. **Custom YOLO model** — If `models/helmet.pt` exists, it's used for accurate helmet detection on the head region of each person.

2. **Robust color analysis (fallback)** — Analyzes only the **crown** (top half, central 60% of the head region) where a helmet shell sits. **Skin pixels are masked out before matching**, so warm/saturated skin tones can never be read as a helmet. Seven narrow helmet-color families are matched (yellow, white, blue, orange, green, red, dark-red) with strict saturation/brightness limits (orange needs high saturation, white needs very high brightness), and a head is accepted only when helmet colors cover **at least 45%** of the crown. Returns a confidence score and a human-readable reason for every person.

Every head region is **validated before classification**: too small, blurred (low Laplacian variance), too dark/bright, low contrast (occlusion), or cropped by the frame edge → the frame is marked unreliable (`CHECKING [ID: N]` in preview) and ignored by the temporal verifier.

For production use, train a custom YOLO helmet model and place it at `models/helmet.pt`.

### Anti-False-Positive Rules

- The **full video is analyzed** — every single frame is checked (default `FRAME_SKIP = 1`), so no violation is missed.
- **No single frame can confirm a violation.** Every tracked person must be detected without a helmet for `VIOLATION_REQUIRED_FRAMES` (30) **consecutive** valid frames before an incident is created.
- Each person's helmet status is **verified over time** per unique track ID (ByteTrack): track history, consecutive counts, and average confidence are tracked. If the prediction flips back to Helmet, the counter resets (e.g. `N-N-N-H-N` → Helmet, no violation).
- Every frame goes through **head-region validation**: heads that are too small, blurred, over/underexposed, occluded, or cropped by the frame edge are ignored — they neither count toward nor reset the counter (continue monitoring).
- Frames below `HELMET_CONFIDENCE_THRESHOLD` (0.90) are ignored, so uncertain classifications don't drive decisions.
- If a tracked person disappears for more than `CONSECUTIVE_GAP_RESET` frames, the counter resets (temporal continuity broken).
- Every captured violation is saved with the analysis reason on the image so you can verify it.
- Use `--preview` to watch the live annotated analysis (green = helmet, red = no helmet, gray = checking, per-person ID) while processing.

## Temporal Verification

A violation is confirmed only after evidence accumulates across **multiple frames** for the same tracked person:

1. **Detect + Track** — persons are detected with YOLO and assigned unique track IDs by ByteTrack.
2. **Validate head** — the head region is checked for size, sharpness, brightness, contrast, and frame-edge cropping. Unreliable frames are skipped.
3. **Classify** — helmet vs. no-helmet with a per-frame confidence score; frames below 0.90 are ignored.
4. **Count consecutively** — no-helmet frames accumulate per track; any helmet frame resets the counter.
5. **Confirm** — after 30 consecutive valid no-helmet frames, the violation is confirmed using the best buffered evidence frame (largest person, sharpest, highest confidence).
6. **Output** — evidence image + warning poster are saved and an incident is recorded (Excel + SQLite).

Design goal: **maximize precision over recall** — delay confirmation rather than raise false alarms.

## Whole-Scene Cross-Verification

When anyone is found without a helmet, the system captures the **entire frame**, not a crop, so you can cross-verify everyone else in the scene too:

- All people in the frame are annotated (green = helmet, red = no helmet, gray = checking) on the evidence image.
- The evidence image header shows the scene summary: `Persons in frame: N | With helmet: X | Without helmet: Y`.
- The best evidence frame is picked per violator using person size, sharpness, and classification confidence (`utils/violation_tracker.py`).
- The Excel report and SQLite database store the cross-verification counts per incident: `Persons in Frame`, `With Helmet`, `Without Helmet`.
- During processing, scene-wide statistics are logged (`SCENE | Cross-check: ...`) so you can see the overall compliance rate across the full video.

## Capture Rules (Single vs. Group)

- **Single violator** — when only one person is confirmed without a helmet, that person is captured alone (`NO HELMET | Track ID: N`).
- **Group violators** — when **2+ people are confirmed without helmets within the same frame window** (`GROUP_CAPTURE_ENABLED`, `GROUP_WINDOW_FRAMES = 15`), the system captures **ONE evidence image** showing all of them together (`NO HELMET (GROUP) | N persons`), with every violator highlighted. Each violator is still recorded as a separate incident in the report/database, all pointing to the same shared evidence image and warning poster.
- A person captured as part of a group (or as a single) is not captured twice — duplicate tracking is automatic.

## Output

### Evidence Images
Full-frame annotated images saved to `output/images/`:
- Entire frame is captured (not a crop) so all people are visible for context
- Green bounding box = person wearing a helmet, red = no helmet (violator)
- Violators are highlighted with a thicker red box and `NO HELMET [ID: N]` label
- A scene summary header is stamped on the image: `Persons in frame: N | With helmet: X | Without helmet: Y`
- The clearest evidence frame is selected automatically (largest violator, sharpest image, highest confidence)
- Filename format: `violation_track{ID}_{video}_{timestamp}.jpg`

### Warning Posters
Warning posters saved to `output/posters/`:
- Red banner with camera info, location, video name, timestamp, track(s), confidence, and analysis reason
- Below the banner: the annotated full-frame evidence showing all violators highlighted
- Filename format: `warning_poster_{track}_{video}_{timestamp}_{timestamp}.jpg`

### Excel Report
Generated at `output/reports/Safety_Report_{video}_{timestamp}.xlsx` with columns:

| Incident ID | Camera Name | Timestamp | Violation Type | Confidence | Track ID |
|-------------|-------------|-----------|----------------|------------|----------|
| INC0001 | Assembly Line 01 | 00:02:14 | Helmet Missing | 0.87 | 15 |

Each row also includes **Violation Image** and **Warning Poster** file paths, plus the scene cross-check columns (`Persons in Frame`, `With Helmet`, `Without Helmet`).

### SQLite Database
All violations stored in `database/violations.db` for querying and analytics.

## Rules

- Only the Person class is processed (COCO class 0)
- Each tracked person is captured only once per appearance
- Low-confidence detections (< threshold) are ignored
- A person is flagged only after `VIOLATION_REQUIRED_FRAMES` consecutive valid no-helmet frames
- Invalid head frames (blur, crop, poor light, occlusion) are ignored and don't drive decisions
- When a person leaves and reappears, they get a new track ID

## Database

`database/violations.db` (SQLite) holds:

| Table | Contents |
|---|---|
| `violations` | One row per confirmed incident — the dashboard's incident history |
| `analysis_runs` | Per-run totals (frames, people tracked, raw detections, incidents) — the denominators behind compliance rate |
| `camera_master` | Camera registry, location, IP, port, AI flag, connection state |
| `supervisor_master` | Supervisors and their alert email addresses |
| `rule_master` | Configurable thresholds applied over `config.py` |
| `violation_history`, `email_log` | Notification audit trail |

Schema changes are applied automatically on startup by the migration step in
`database/db_manager.py`, so an existing database is upgraded in place.

For production, point the same schema at PostgreSQL.

## Future Phases

- **Phase 2:** Live RTSP/IP camera streams with decoding, multi-camera support, employee recognition (InsightFace — RetinaFace detection + ArcFace embedding)
- **Phase 3:** Microsoft Teams and SMS notification channels alongside email
- **Phase 4:** Additional PPE detection (vests, gloves, goggles, shoes)

The dashboard already models both phases: the AI Models page shows the Phase 2
recognition stack as planned-but-disabled, and camera panels switch from
"recorded input" to live streaming without a redesign.

## License

For internal demonstration purposes only.
