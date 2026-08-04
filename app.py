import cv2
import logging
import argparse
import sys
from pathlib import Path
from datetime import datetime

import config as cfg
from detector import YOLODetector
from tracker import PersonTracker
from report import ReportGenerator
from database import DatabaseManager, RuleManager
from notification import NotificationManager
from utils import VideoReader, save_violation_image, annotate_frame, generate_warning_poster
from utils import ViolationTracker, extract_video_metadata

logging.basicConfig(
    level=getattr(logging, cfg.LOG_LEVEL),
    format=cfg.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(cfg.LOGS_DIR / "processing.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)


class HelmetDetectionSystem:
    def __init__(self):
        self.config = cfg
        self.db = DatabaseManager(
            cfg.DATABASE_DIR / "violations.db", seed_defaults=cfg.DB_SEED_DEFAULTS
        )
        self._apply_rule_overrides()
        self.video_reader = VideoReader(self.config)
        self.detector = YOLODetector(self.config)
        self.tracker = PersonTracker(self.config)
        self.report_generator = ReportGenerator(self.config)
        self.notifier = NotificationManager(self.config, db=self.db)
        self.video_fps = 0

    def _apply_rule_overrides(self):
        if not getattr(cfg, "RULE_OVERRIDE_ENABLED", True):
            return
        try:
            RuleManager(self.db).apply_config_overrides(cfg, {
                "helmet missing": "VIOLATION_REQUIRED_FRAMES",
                "helmet confidence": "HELMET_CONFIDENCE_THRESHOLD",
            })
        except Exception as exc:
            logger.warning(f"Could not apply RULE_MASTER overrides: {exc}")

    def process_video(self, video_path, camera_name=None, camera_id=None, location=None, preview=False):
        cap, video_info = self.video_reader.open(video_path)
        video_name = video_info["name"]
        total_frames = video_info["total_frames"]
        fps = video_info["fps"]
        self.video_fps = fps

        if not (camera_name and camera_id and location):
            metadata = extract_video_metadata(video_path, self.config)
        else:
            metadata = {}
        camera_name = camera_name or metadata.get("camera_name") or self.config.DEFAULT_CAMERA_NAME
        camera_id = camera_id or metadata.get("camera_id") or self.config.DEFAULT_CAMERA_ID
        location = location or metadata.get("location") or self.config.DEFAULT_LOCATION

        frame_count = 0
        processed_count = 0
        violation_count = 0
        scene_persons_total = 0
        scene_helmet_ok = 0
        scene_no_helmet = 0
        start_time = datetime.now()

        logger.info("=" * 60)
        logger.info(f"Processing started: {video_name}")
        logger.info(f"Camera: {camera_name} ({camera_id}) - {location}")
        logger.info(f"Total frames: {total_frames} | FPS: {fps:.2f}")
        logger.info(
            f"Frame skip: {self.config.FRAME_SKIP} | Person conf: {self.config.CONFIDENCE_THRESHOLD} | "
            f"Helmet conf: {self.config.HELMET_CONFIDENCE_THRESHOLD}"
        )
        logger.info(
            f"Temporal verification: {self.config.VIOLATION_REQUIRED_FRAMES} consecutive no-helmet frames "
            f"(gap reset {self.config.CONSECUTIVE_GAP_RESET}) | Group window: {self.config.GROUP_WINDOW_FRAMES} frames"
        )
        logger.info("=" * 60)

        self.violation_tracker = ViolationTracker(self.config)
        self.confirmed_tracks = {}
        self.recent_groups = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1

            if frame_count % self.config.FRAME_SKIP != 0:
                continue

            frame = self.video_reader.resize_frame(frame)
            processed_count += 1

            persons = self.detector.detect(frame)
            tracked_persons = self.tracker.update(persons, frame)
            video_time = self._get_video_timestamp(frame_count, fps)

            persons_info = [
                {
                    "track_id": p["track_id"],
                    "bbox": list(p["bbox"]),
                    "has_helmet": bool(p["has_helmet"]),
                    "helmet_status": self._helmet_status(p),
                    "confidence": float(p["confidence"]),
                }
                for p in tracked_persons
            ]

            scene_persons_total += len(persons_info)
            scene_helmet_ok += sum(1 for p in persons_info if p["helmet_status"] == "helmet")
            scene_no_helmet += sum(1 for p in persons_info if p["helmet_status"] == "no")

            if preview:
                cv2.imshow("Helmet Detection Analysis", annotate_frame(frame, persons_info))
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            events = self.violation_tracker.update(
                tracked_persons, frame, frame_count, video_time
            )
            if events:
                self._save_confirmations(
                    events, video_name, camera_name, camera_id, location,
                )
                violation_count += len(events)

            if processed_count % 100 == 0:
                progress = (frame_count / total_frames) * 100
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info(
                    f"Progress: {frame_count}/{total_frames} ({progress:.1f}%) | "
                    f"Violations: {violation_count} | "
                    f"Elapsed: {elapsed:.1f}s"
                )
                if scene_persons_total:
                    logger.info(
                        f"SCENE | Cross-check: {scene_persons_total} person-frames | "
                        f"{scene_helmet_ok} with helmet ({scene_helmet_ok / scene_persons_total:.0%}) | "
                        f"{scene_no_helmet} without helmet ({scene_no_helmet / scene_persons_total:.0%})"
                    )

        if preview:
            cv2.destroyAllWindows()

        self.video_reader.release(cap)
        elapsed = (datetime.now() - start_time).total_seconds()

        report_path = self.report_generator.generate_excel_report(video_name)

        logger.info("=" * 60)
        logger.info(f"Processing complete: {video_name}")
        logger.info(f"Frames processed: {processed_count}")
        logger.info(f"Violations detected: {violation_count}")
        if scene_persons_total:
            logger.info(
                f"Scene cross-check: {scene_persons_total} person-frames | "
                f"{scene_helmet_ok} with helmet | {scene_no_helmet} without helmet"
            )
        logger.info(f"Total time: {elapsed:.1f}s")
        if report_path:
            logger.info(f"Report saved: {report_path}")
        logger.info(f"Images saved in: {self.config.IMAGES_DIR}")
        logger.info("=" * 60)

        return {
            "video_name": video_name,
            "total_frames": total_frames,
            "frames_processed": processed_count,
            "violations": violation_count,
            "elapsed_seconds": elapsed,
            "report_path": report_path,
        }

    def _helmet_status(self, person):
        analysis = person.get("helmet_analysis") or {}
        if not analysis.get("head_valid", True):
            return "unknown"
        return "helmet" if bool(person["has_helmet"]) else "no"

    def _save_confirmations(self, events, video_name, camera_name, camera_id, location):
        window = self.config.GROUP_WINDOW_FRAMES
        uncaptured = [e for e in events if not self.tracker.was_captured(e.track_id)]
        if not uncaptured:
            return

        first = uncaptured[0]
        cand = first.candidate

        reuse = next(
            (g for e in uncaptured for g in self.recent_groups if e.track_id in g["ids"]),
            None,
        )
        if reuse:
            for e in uncaptured:
                self._finalize_confirmation(
                    e, reuse["image"], reuse["poster"], video_name, camera_name, camera_id, location,
                )
            return

        highlight = [e.track_id for e in uncaptured]
        if self.config.GROUP_CAPTURE_ENABLED:
            for p in cand.persons_info:
                if p.get("helmet_status") != "no" or p["track_id"] in highlight:
                    continue
                prev = self.confirmed_tracks.get(p["track_id"])
                if prev and abs(prev["frame"] - cand.frame_index) <= window:
                    highlight.append(p["track_id"])

        is_group = len(highlight) > 1
        label = "+".join(map(str, highlight)) if is_group else str(first.track_id)
        title = (
            f"NO HELMET (GROUP) | {len(highlight)} persons | Time {cand.video_time}"
            if is_group else f"NO HELMET | Track {first.track_id} | Time {cand.video_time}"
        )

        image_path = save_violation_image(
            cand.frame, cand.persons_info, label,
            self.config, video_name, cand.video_time, cand.reason,
            highlight_ids=highlight, title=title,
        )
        poster_path = generate_warning_poster(
            cand.frame, cand.persons_info, highlight, self.config,
            video_name, cand.video_time, camera_name, camera_id,
            location, label, first.confidence, cand.reason,
        )

        for e in uncaptured:
            self._finalize_confirmation(
                e, image_path, poster_path, video_name, camera_name, camera_id, location,
            )

        if is_group:
            self.recent_groups.append({
                "frame": cand.frame_index, "ids": list(highlight),
                "image": image_path, "poster": poster_path,
            })
        self.recent_groups = [
            g for g in self.recent_groups
            if cand.frame_index - g["frame"] <= window
        ]

        logger.info(
            f"SCENE | Frame {cand.frame_index} | {len(cand.persons_info)} persons in frame | "
            f"{sum(1 for p in cand.persons_info if p.get('helmet_status') == 'helmet')} with helmet | "
            f"{sum(1 for p in cand.persons_info if p.get('helmet_status') == 'no')} without helmet | "
            f"capture: {label}"
        )

    def _finalize_confirmation(self, event, image_path, poster_path,
                               video_name, camera_name, camera_id, location):
        track_id = event.track_id
        if self.tracker.was_captured(track_id):
            return
        cand = event.candidate

        with_helmet = sum(1 for p in cand.persons_info if p.get("helmet_status") == "helmet")
        no_helmet = sum(1 for p in cand.persons_info if p.get("helmet_status") == "no")

        incident = {
            "camera_name": camera_name,
            "camera_id": camera_id,
            "location": location,
            "video_name": video_name,
            "image_path": image_path or "",
            "poster_path": poster_path or "",
            "timestamp": cand.video_time,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "confidence": event.confidence,
            "track_id": track_id,
            "scene_persons": len(cand.persons_info),
            "scene_helmet": with_helmet,
            "scene_no_helmet": no_helmet,
            "fps": getattr(self, "video_fps", 0),
        }

        self.report_generator.add_incident(incident)
        self.notifier.notify(incident, cand.frame)
        self.tracker.mark_captured(track_id)
        self.confirmed_tracks[track_id] = {
            "frame": cand.frame_index, "image": image_path, "poster": poster_path,
        }

        logger.info(
            f"VIOLATION | Track ID: {track_id} | "
            f"Time: {cand.video_time} | Confidence: {event.confidence:.2f} | "
            f"Frame: {cand.frame_index} | Poster: {Path(poster_path).name if poster_path else 'n/a'}"
        )

    def _get_video_timestamp(self, frame_count, fps):
        if fps <= 0:
            return "00:00:00"
        total_seconds = int(frame_count / fps)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _find_videos(directory):
    video_exts = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    return sorted([
        v for v in Path(directory).iterdir()
        if v.is_file() and v.suffix.lower() in video_exts
    ])


def _interactive_select():
    videos = _find_videos(cfg.VIDEOS_DIR)
    other_dir = None

    while True:
        if videos:
            print("\n" + "=" * 60)
            print("  AVAILABLE VIDEOS")
            print("=" * 60)
            for i, v in enumerate(videos, 1):
                size = v.stat().st_size / (1024 * 1024)
                print(f"  [{i}] {v.name} ({size:.1f} MB)")
            print(f"  [{len(videos) + 1}] Browse other location")
            print(f"  [{len(videos) + 2}] Exit")
            print("=" * 60)

            choice = input("\nSelect video: ").strip()
            try:
                idx = int(choice)
                if 1 <= idx <= len(videos):
                    return str(videos[idx - 1])
                elif idx == len(videos) + 1:
                    other_dir = input("Enter folder path: ").strip()
                    if other_dir:
                        videos = _find_videos(other_dir)
                    continue
                elif idx == len(videos) + 2:
                    print("Exiting.")
                    sys.exit(0)
            except ValueError:
                pass
        else:
            print(f"\nNo videos found in videos/")
            other_dir = input("Enter video folder path (or 'q' to quit): ").strip()
            if other_dir.lower() == "q":
                sys.exit(0)
            if other_dir:
                videos = _find_videos(other_dir)
                if not videos:
                    print(f"No video files found in {other_dir}")
                    videos = _find_videos(cfg.VIDEOS_DIR)
                    continue
                return str(videos[0])

        print("Invalid selection, try again")


def main():
    parser = argparse.ArgumentParser(
        description="AI-Based Helmet Detection and Safety Violation Reporting System"
    )
    parser.add_argument("video", nargs="?", help="Path to CCTV video file")
    parser.add_argument("--camera-name", default=None, help="Camera name")
    parser.add_argument("--camera-id", default=None, help="Camera ID")
    parser.add_argument("--location", default=None, help="Location")
    parser.add_argument("--list-videos", action="store_true", help="List available videos")
    parser.add_argument("--conf", type=float, default=None, help="Confidence threshold (0-1)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive video selector")
    parser.add_argument("--preview", action="store_true", help="Show live annotated frame preview window")

    args = parser.parse_args()

    if args.conf is not None:
        cfg.CONFIDENCE_THRESHOLD = max(0.0, min(1.0, args.conf))
        logger.info(f"Confidence threshold set to: {cfg.CONFIDENCE_THRESHOLD}")

    if args.list_videos:
        videos = _find_videos(cfg.VIDEOS_DIR)
        if videos:
            print("\nAvailable videos:")
            for v in videos:
                size_mb = v.stat().st_size / (1024 * 1024)
                print(f"  {v.name} ({size_mb:.1f} MB)")
        else:
            print(f"\nNo videos found in {cfg.VIDEOS_DIR}")
            print("Place .mp4/.avi/.mov files in the videos/ directory")
        return

    if args.interactive or not args.video:
        video_path = _interactive_select()
    else:
        video_path = args.video

    system = HelmetDetectionSystem()
    result = system.process_video(
        video_path,
        camera_name=args.camera_name,
        camera_id=args.camera_id,
        location=args.location,
        preview=args.preview,
    )

    print("\n" + "=" * 60)
    print("PROCESSING SUMMARY")
    print("=" * 60)
    print(f"  Video:          {result['video_name']}")
    print(f"  Total frames:   {result['total_frames']}")
    print(f"  Processed:      {result['frames_processed']}")
    print(f"  Violations:     {result['violations']}")
    print(f"  Time elapsed:   {result['elapsed_seconds']:.1f}s")
    if result["report_path"]:
        print(f"  Report:         {result['report_path']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
