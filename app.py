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
from utils import VideoReader, save_violation_image

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
        self.video_reader = VideoReader(self.config)
        self.detector = YOLODetector(self.config)
        self.tracker = PersonTracker(self.config)
        self.report_generator = ReportGenerator(self.config)

    def process_video(self, video_path, camera_name=None, camera_id=None, location=None):
        cap, video_info = self.video_reader.open(video_path)
        video_name = video_info["name"]
        total_frames = video_info["total_frames"]
        fps = video_info["fps"]

        camera_name = camera_name or self.config.DEFAULT_CAMERA_NAME
        camera_id = camera_id or self.config.DEFAULT_CAMERA_ID
        location = location or self.config.DEFAULT_LOCATION

        frame_count = 0
        processed_count = 0
        violation_count = 0
        start_time = datetime.now()

        logger.info("=" * 60)
        logger.info(f"Processing started: {video_name}")
        logger.info(f"Camera: {camera_name} ({camera_id}) - {location}")
        logger.info(f"Total frames: {total_frames} | FPS: {fps:.2f}")
        logger.info(f"Frame skip: {self.config.FRAME_SKIP} | Confidence threshold: {self.config.CONFIDENCE_THRESHOLD}")
        logger.info("=" * 60)

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

            for tp in tracked_persons:
                if tp["has_helmet"]:
                    continue

                if not tp["is_new_capture"]:
                    continue

                if self.tracker.was_captured(tp["track_id"]):
                    continue

                timestamp = datetime.now().strftime("%H:%M:%S")
                date = datetime.now().strftime("%Y-%m-%d")
                video_time = self._get_video_timestamp(frame_count, fps)

                image_path = save_violation_image(
                    frame, tp["bbox"], tp["track_id"],
                    self.config, video_name,
                )

                incident = {
                    "camera_name": camera_name,
                    "camera_id": camera_id,
                    "location": location,
                    "video_name": video_name,
                    "image_path": image_path or "",
                    "timestamp": video_time,
                    "date": date,
                    "confidence": tp["confidence"],
                    "track_id": tp["track_id"],
                }

                self.report_generator.add_incident(incident)
                self.tracker.mark_captured(tp["track_id"])
                violation_count += 1

                logger.info(
                    f"VIOLATION | Track ID: {tp['track_id']} | "
                    f"Time: {video_time} | Confidence: {tp['confidence']:.2f}"
                )

            if processed_count % 100 == 0:
                progress = (frame_count / total_frames) * 100
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info(
                    f"Progress: {frame_count}/{total_frames} ({progress:.1f}%) | "
                    f"Violations: {violation_count} | "
                    f"Elapsed: {elapsed:.1f}s"
                )

        self.video_reader.release(cap)
        elapsed = (datetime.now() - start_time).total_seconds()

        report_path = self.report_generator.generate_excel_report(video_name)

        logger.info("=" * 60)
        logger.info(f"Processing complete: {video_name}")
        logger.info(f"Frames processed: {processed_count}")
        logger.info(f"Violations detected: {violation_count}")
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
