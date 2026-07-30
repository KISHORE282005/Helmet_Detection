import cv2
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


class VideoReader:
    def __init__(self, config):
        self.config = config

    def open(self, video_path):
        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported format: {path.suffix}. "
                f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
            )

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 0

        info = {
            "path": str(path),
            "name": path.name,
            "fps": fps,
            "total_frames": total_frames,
            "width": width,
            "height": height,
            "duration": duration,
        }
        logger.info(f"Video opened: {path.name} ({width}x{height}, {fps:.2f} fps, {duration:.1f}s)")
        return cap, info

    def resize_frame(self, frame):
        h, w = frame.shape[:2]
        if w > self.config.RESIZE_WIDTH:
            scale = self.config.RESIZE_WIDTH / w
            new_w = self.config.RESIZE_WIDTH
            new_h = int(h * scale)
            return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return frame

    def release(self, cap):
        if cap is not None:
            cap.release()
            logger.info("Video capture released")
