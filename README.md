# AI-Based Helmet Detection and Automated Safety Violation Reporting System

A Proof-of-Concept system that analyzes CCTV footage to detect workers without safety helmets, captures evidence images, and generates automated violation reports.

## System Architecture

```
CCTV Video → Frame Extraction → YOLO Person Detection → Helmet Check
                                                              │
                                                   ┌──────────┴──────────┐
                                                   │                    │
                                               Has Helmet         No Helmet
                                                   │                    │
                                                Ignore          ByteTrack ID
                                                                     │
                                                              Duplicate Check
                                                                     │
                                                         ┌──────────┴──────────┐
                                                         │                    │
                                                     Captured           New Track
                                                         │                    │
                                                      Ignore         Save Image
                                                                     │
                                                              Record Incident
                                                                     │
                                                          Excel Report + SQLite
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

## GUI Usage

1. Click **Upload Video** — select a CCTV video file
2. (Optional) Edit Camera Name / ID / Location
3. Click **Start Processing**
4. View live log output; summary popup appears on completion

## CLI Usage

```
usage: app.py [-h] [--camera-name CAMERA_NAME] [--camera-id CAMERA_ID]
              [--location LOCATION] [--list-videos] [--conf CONF]
              [--interactive] [video]

positional arguments:
  video                 Path to CCTV video file

options:
  -h, --help            Show this help
  --camera-name NAME    Camera name (default: Assembly Line 01)
  --camera-id ID        Camera ID (default: CAM001)
  --location LOC        Location (default: Production Area A)
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
├── models/              YOLO model files (*.pt)
│   └── yolo11n.pt       Pre-trained person detector (auto-downloaded)
├── videos/              Place CCTV videos here
├── output/
│   ├── images/          Violation evidence images (annotated)
│   ├── reports/         Generated Excel safety reports
│   └── logs/            Processing logs
├── database/
│   └── violations.db    SQLite violation database
├── detector/
│   └── yolo_detector.py YOLOv11 person + helmet detection
├── tracker/
│   └── tracker.py       ByteTrack multi-object tracking
├── report/
│   └── report_generator.py  Excel + SQLite report generation
└── utils/
    ├── video_utils.py   Video I/O, frame resizing
    └── image_utils.py   Violation image capture & annotation
```

## Configuration

Edit `config.py` to adjust:

| Setting | Default | Description |
|---------|---------|-------------|
| `CONFIDENCE_THRESHOLD` | `0.60` | Minimum detection confidence |
| `FRAME_SKIP` | `3` | Process every Nth frame (higher = faster) |
| `RESIZE_WIDTH` | `1280` | Resize frame width (preserves aspect ratio) |
| `MAX_TRACK_AGE` | `60` | Max frames to keep lost tracks |
| `DEFAULT_CAMERA_NAME` | `Assembly Line 01` | Default camera label |
| `HELMET_MODEL_PATH` | `models/helmet.pt` | Custom helmet model (optional) |

## Helmet Detection

The system uses two methods (in priority order):

1. **Custom YOLO model** — If `models/helmet.pt` exists, it's used for accurate helmet detection on the head region of each person.

2. **HSV color analysis (fallback)** — Detects common safety helmet colors (yellow, white, blue, orange) in the upper head region. Used when no custom model is available.

For production use, train a custom YOLO helmet model and place it at `models/helmet.pt`.

## Output

### Evidence Images
Annotated images saved to `output/images/`:
- Red bounding box around the violator
- "NO HELMET [ID: N]" label with tracking ID
- Filename format: `violation_track{ID}_{video}_{timestamp}.jpg`

### Excel Report
Generated at `output/reports/Safety_Report_{video}_{timestamp}.xlsx` with columns:

| Incident ID | Camera Name | Timestamp | Violation Type | Confidence | Track ID |
|-------------|-------------|-----------|----------------|------------|----------|
| INC0001 | Assembly Line 01 | 00:02:14 | Helmet Missing | 0.87 | 15 |

### SQLite Database
All violations stored in `database/violations.db` for querying and analytics.

## Rules

- Only the Person class is processed (COCO class 0)
- Each tracked person is captured only once per appearance
- Low-confidence detections (< threshold) are ignored
- When a person leaves and reappears, they get a new track ID

## Future Phases

- **Phase 2:** Live RTSP/IP camera streams, multi-camera support
- **Phase 3:** Face recognition (InsightFace), email/SMS alerts
- **Phase 4:** Analytics dashboard, additional PPE detection (vests, gloves, goggles, shoes)

## License

For internal demonstration purposes only.
