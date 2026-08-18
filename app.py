import cv2
import logging
import argparse
import signal
import sys
import time
import uuid
from pathlib import Path
from datetime import datetime

import config as cfg
from detector import YOLODetector
from tracker import PersonTracker
from report import ReportGenerator
from database import DatabaseManager, RuleManager
from notification import NotificationManager
from nva import ActivityTracker, build_recommendations, summarize
from utils import VideoReader, save_violation_image, annotate_frame, generate_warning_poster
from utils import ViolationTracker, extract_video_metadata, is_stream_source

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

    def process_video(self, video_path, camera_name=None, camera_id=None, location=None,
                      preview=False, progress_callback=None, analysis_id="",
                      should_stop=None, display_name=None):
        """Analyze one video end to end.

        `video_path` is either a file on disk or a live camera URL
        (rtsp://...); the only differences are that a stream has no frame
        count, is timestamped against the wall clock, and is reopened rather
        than abandoned when a read fails.

        progress_callback(dict) is invoked periodically with live counters so a
        UI can render real progress; should_stop() lets a caller cancel the run.
        display_name overrides the name recorded on incidents, so an upload
        stored under a generated filename still reports the operator's original.
        """
        cap, video_info = self.video_reader.open(video_path)
        is_stream = bool(video_info.get("is_stream"))
        video_name = display_name or video_info["name"]
        total_frames = video_info["total_frames"]
        fps = video_info["fps"]
        self.video_fps = fps

        # A stream has no filename to parse, and its camera details are always
        # supplied by the caller from the camera record.
        if not is_stream and not (camera_name and camera_id and location):
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
        if is_stream:
            logger.info(f"Source: LIVE STREAM {video_info['path']} | FPS: {fps:.2f}")
        else:
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
        # Same tracks, second question: not "is this person safe" but "is this
        # person adding value". Runs off the existing trajectories, so it adds
        # arithmetic rather than another model.
        self.activity_tracker = ActivityTracker(self.config)
        self.confirmed_tracks = {}
        self.recent_groups = []
        self.analysis_id = analysis_id
        # A CLI run has no job id, but its activity segments still need to be
        # grouped, so give it one rather than filing them under "".
        nva_run_id = analysis_id or f"cli-{uuid.uuid4().hex[:8]}"
        self.recorded_incidents = []
        self.report_generator.incidents = []
        self.report_generator.nva_segments = []
        self.report_generator.nva_breakdown = None
        unique_tracks = set()
        cancelled = False
        position_seconds = 0.0

        def emit_progress(done=False):
            if not progress_callback:
                return
            elapsed_now = (datetime.now() - start_time).total_seconds()
            progress_callback({
                "nva": self.activity_tracker.live_totals(),
                "frames_total": total_frames,
                "frames_read": frame_count,
                "frames_analyzed": processed_count,
                "progress": (frame_count / total_frames) if total_frames else 0.0,
                "people_detected": len(unique_tracks),
                "person_frames": scene_persons_total,
                "raw_detections": scene_no_helmet,
                "compliant_frames": scene_helmet_ok,
                "incidents": violation_count,
                "processing_fps": (processed_count / elapsed_now) if elapsed_now > 0 else 0.0,
                "elapsed_seconds": elapsed_now,
                "done": done,
            })

        max_reconnects = int(getattr(self.config, "RTSP_RECONNECT_ATTEMPTS", 0)) if is_stream else 0
        reconnect_delay = float(getattr(self.config, "RTSP_RECONNECT_DELAY", 3.0))
        max_duration = float(getattr(self.config, "LIVE_MAX_DURATION_SECONDS", 0)) if is_stream else 0
        reconnects = 0

        while True:
            if should_stop and should_stop():
                cancelled = True
                logger.info("Processing cancelled by caller")
                break

            elapsed_so_far = (datetime.now() - start_time).total_seconds()
            if max_duration and elapsed_so_far >= max_duration:
                logger.info(f"Live session reached its {max_duration:.0f}s limit")
                break

            ret, frame = (False, None) if cap is None else cap.read()
            if not ret:
                # For a file this is the end of the footage. For a stream it
                # almost always means the network dropped, so reopen instead of
                # reporting a complete run over partial coverage.
                if reconnects >= max_reconnects:
                    if is_stream:
                        logger.warning(
                            f"Stream ended after {reconnects} reconnect attempt(s)"
                        )
                    break
                reconnects += 1
                cap = self._reconnect_stream(
                    cap, video_path, reconnect_delay, reconnects, max_reconnects
                )
                continue

            if reconnects:
                # A decoded frame means the link came back; allow the full
                # retry budget again for any later drop.
                logger.info("Stream recovered")
                reconnects = 0

            frame_count += 1

            if frame_count % self.config.FRAME_SKIP != 0:
                continue

            frame = self.video_reader.resize_frame(frame)
            processed_count += 1

            persons = self.detector.detect(frame)
            tracked_persons = self.tracker.update(persons, frame)
            # Offsets into a recording are frame-based; a live feed is timed
            # against the clock, because dropped frames would otherwise make
            # the incident time drift away from when it actually happened.
            position_seconds = (
                elapsed_so_far if is_stream
                else (frame_count / fps if fps > 0 else 0.0)
            )
            video_time = self._format_timestamp(position_seconds)

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
            unique_tracks.update(p["track_id"] for p in persons_info)

            if preview:
                cv2.imshow("Helmet Detection Analysis", annotate_frame(frame, persons_info))
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            self.activity_tracker.update(tracked_persons, video_time, position_seconds)

            events = self.violation_tracker.update(
                tracked_persons, frame, frame_count, video_time
            )
            if events:
                self._save_confirmations(
                    events, video_name, camera_name, camera_id, location,
                )
                violation_count += len(events)

            if processed_count % 10 == 0:
                emit_progress()

            if processed_count % 100 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                if total_frames:
                    progress = (frame_count / total_frames) * 100
                    position = f"Progress: {frame_count}/{total_frames} ({progress:.1f}%)"
                else:
                    # A live stream has no end to measure against.
                    position = f"Live: {frame_count} frames received"
                logger.info(
                    f"{position} | "
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

        # Close any activity still in progress before summarising, so the last
        # segment of the video is not silently dropped.
        self.activity_tracker.finalize(position_seconds)
        nva = self._finalize_activity_analysis(
            nva_run_id, video_name, camera_name, camera_id, location,
            "rtsp" if is_stream else "recording",
        )

        emit_progress(done=True)

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
        self._log_activity_summary(nva)
        logger.info(f"Total time: {elapsed:.1f}s")
        if report_path:
            logger.info(f"Report saved: {report_path}")
        logger.info(f"Images saved in: {self.config.IMAGES_DIR}")
        logger.info("=" * 60)

        return {
            "video_name": video_name,
            "camera_name": camera_name,
            "camera_id": camera_id,
            "location": location,
            "is_stream": is_stream,
            "source_type": "rtsp" if is_stream else "recording",
            "total_frames": total_frames,
            "frames_processed": processed_count,
            "video_fps": fps,
            # `violations` counts confirmed incidents (one per tracked person),
            # `raw_detections` counts every no-helmet person-frame. The gap
            # between the two is what duplicate suppression removed.
            "violations": violation_count,
            "raw_detections": scene_no_helmet,
            "person_frames": scene_persons_total,
            "compliant_frames": scene_helmet_ok,
            "people_detected": len(unique_tracks),
            "incidents": list(self.recorded_incidents),
            # Value-stream analysis: where the observed operator time went, and
            # what to do about the part of it that added no value.
            "nva": nva,
            "nva_run_id": nva_run_id,
            "elapsed_seconds": elapsed,
            "processing_fps": (processed_count / elapsed) if elapsed > 0 else 0.0,
            "cancelled": cancelled,
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
            "analysis_id": getattr(self, "analysis_id", ""),
            "confirm_frames": int(getattr(self.config, "VIOLATION_REQUIRED_FRAMES", 0)),
        }

        record = self.report_generator.add_incident(incident)
        if record:
            self.recorded_incidents.append(record)
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

    def _finalize_activity_analysis(self, run_id, video_name, camera_name,
                                    camera_id, location, source_type):
        """Summarise, store and act on the run's activity segments.

        Returns the value-stream breakdown with its recommendations attached,
        or None when NVA analysis is switched off.
        """
        tracker = self.activity_tracker
        if not tracker.enabled:
            return None

        breakdown = summarize(
            tracker.segments,
            observed_seconds=tracker.observed_seconds,
            tracks=len(tracker.tracks_seen),
        )
        breakdown["run_id"] = run_id
        breakdown["recommendations"] = build_recommendations(breakdown, self.config)

        records = [
            {
                "run_id": run_id,
                "camera_id": camera_id,
                "camera_name": camera_name,
                "location": location,
                "video_name": video_name,
                "source_type": source_type,
                **segment.to_dict(),
            }
            for segment in tracker.segments
        ]
        self.report_generator.nva_segments = records
        self.report_generator.nva_breakdown = breakdown

        if records:
            try:
                self.db.insert_nva_activities(records)
            except Exception as exc:
                logger.error(f"Could not store NVA activity segments: {exc}")

        return breakdown

    @staticmethod
    def _log_activity_summary(breakdown):
        """Print the value-stream result and the top actions to the log."""
        if not breakdown or not breakdown.get("classified_seconds"):
            return

        logger.info(
            f"VALUE STREAM | Observed {breakdown['observed_duration']} of operator time | "
            f"classified {breakdown['classified_duration']}"
        )
        for row in breakdown["value_split"]:
            logger.info(
                f"  {row['value_class']:<5} {row['label']:<20} "
                f"{row['duration']:>9} ({row['share']:.1f}%)"
            )
        for row in breakdown["by_activity"]:
            logger.info(
                f"  ACTIVITY | {row['label']:<36} {row['duration']:>9} "
                f"({row['share']:.1f}%) over {row['occurrences']} occurrence(s)"
            )
        for index, action in enumerate(breakdown.get("recommendations", []), 1):
            logger.info(
                f"  RECOMMENDATION {index} [{action['severity'].upper()}] {action['title']}"
            )
            logger.info(f"      {action['observation']}")
            logger.info(f"      Lean tool: {action['lean_tool']}")

    def _reconnect_stream(self, cap, url, delay, attempt, total_attempts):
        """Reopen a dropped stream. Returns the new capture, or None to retry.

        Returning None is not a failure the caller has to handle: the read loop
        treats a missing capture as a failed read, so the next iteration simply
        spends another attempt from the same budget.
        """
        safe_url = self.config.redact_rtsp_url(url) if is_stream_source(url) else str(url)
        logger.warning(
            f"Stream read failed — reconnecting to {safe_url} "
            f"({attempt}/{total_attempts}) in {delay:.1f}s"
        )
        self.video_reader.release(cap)
        time.sleep(delay)
        try:
            new_cap, _ = self.video_reader.open(url)
            return new_cap
        except Exception as exc:
            logger.warning(f"Reconnect attempt {attempt} failed: {exc}")
            return None

    @staticmethod
    def _format_timestamp(total_seconds):
        total_seconds = int(max(0, total_seconds))
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
    parser.add_argument("video", nargs="?", help="Path to CCTV video file, or an rtsp:// URL")
    parser.add_argument("--camera-name", default=None, help="Camera name")
    parser.add_argument("--camera-id", default=None, help="Camera ID")
    parser.add_argument("--location", default=None, help="Location")
    parser.add_argument("--list-videos", action="store_true", help="List available videos")
    parser.add_argument("--conf", type=float, default=None, help="Confidence threshold (0-1)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive video selector")
    parser.add_argument("--preview", action="store_true", help="Show live annotated frame preview window")
    parser.add_argument("--camera-ip", default=None,
                        help="Hikvision camera IP — analyse its live RTSP stream instead of a file")
    parser.add_argument("--rtsp-port", type=int, default=None, help="RTSP port (default 554)")
    parser.add_argument("--rtsp-channel", default=None,
                        help="Hikvision channel: 101 = main stream, 102 = sub stream")
    parser.add_argument("--duration", type=float, default=None,
                        help="Stop live analysis after N seconds (default: run until Ctrl-C)")

    args = parser.parse_args()

    if args.conf is not None:
        cfg.CONFIDENCE_THRESHOLD = max(0.0, min(1.0, args.conf))
        logger.info(f"Confidence threshold set to: {cfg.CONFIDENCE_THRESHOLD}")

    if args.duration is not None:
        cfg.LIVE_MAX_DURATION_SECONDS = max(0.0, args.duration)

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

    if args.camera_ip:
        video_path = cfg.rtsp_url(
            args.camera_ip, port=args.rtsp_port, channel=args.rtsp_channel
        )
        logger.info(f"Live source: {cfg.redact_rtsp_url(video_path)}")
        if not cfg.RTSP_USERNAME:
            logger.warning(
                "RTSP_USERNAME is not set in .env — this only works if the camera "
                "allows anonymous streaming, which Hikvision disables by default."
            )
    elif args.interactive or not args.video:
        video_path = _interactive_select()
    else:
        video_path = args.video

    # Ctrl-C on a live run should end the session the same way the dashboard's
    # stop button does, so the report and incident records are still written.
    stop_requested = []
    signal.signal(signal.SIGINT, lambda *_: stop_requested.append(True))

    system = HelmetDetectionSystem()
    result = system.process_video(
        video_path,
        camera_name=args.camera_name,
        camera_id=args.camera_id,
        location=args.location,
        preview=args.preview,
        should_stop=lambda: bool(stop_requested),
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
    _print_nva_summary(result.get("nva"))
    print("=" * 60)


def _print_nva_summary(breakdown):
    """Value-stream result and the ranked actions, for the CLI operator."""
    if not breakdown or not breakdown.get("classified_seconds"):
        return

    print("\n" + "-" * 60)
    print("VALUE STREAM (NVA ANALYSIS)")
    print("-" * 60)
    print(f"  Observed operator time: {breakdown['observed_duration']}")
    print(f"  Classified:             {breakdown['classified_duration']}")
    for row in breakdown["value_split"]:
        print(f"  {row['label']:<20} {row['duration']:>9}  {row['share']:>5.1f}%")

    print("\n  Activity breakdown")
    for row in breakdown["by_activity"]:
        marker = "NVA " if row["value_class"] == "NVA" else "    "
        print(
            f"   {marker}{row['label']:<36} {row['duration']:>9} "
            f"{row['share']:>5.1f}%  x{row['occurrences']}"
        )

    recommendations = breakdown.get("recommendations") or []
    if not recommendations:
        print("\n  No waste crossed the reporting threshold — nothing to action.")
        return

    print("\n  Recommendations (highest measured cost first)")
    for index, action in enumerate(recommendations, 1):
        print(f"\n   {index}. [{action['severity'].upper()}] {action['title']}")
        if action.get("waste"):
            print(f"      Waste:  {action['waste']}")
        print(f"      Seen:   {action['observation']}")
        print(f"      Tool:   {action['lean_tool']}")
        for step in action["actions"]:
            print(f"        - {step}")
        print(f"      Impact: {action['expected_impact']}")


if __name__ == "__main__":
    main()
