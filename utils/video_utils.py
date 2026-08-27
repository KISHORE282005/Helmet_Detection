import os
import cv2
import logging
from pathlib import Path

import config as cfg

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
# Schemes that mean "network stream" rather than "file on disk". Anything in
# this list skips the extension check, because a live URL has no extension.
STREAM_SCHEMES = ("rtsp://", "rtsps://", "http://", "https://", "rtmp://")


def is_stream_source(source):
    """True when the source is a live network stream rather than a local file."""
    return isinstance(source, str) and source.strip().lower().startswith(STREAM_SCHEMES)


def stream_label(url):
    """A short, credential-free name for a stream, safe to log or display."""
    redacted = cfg.redact_rtsp_url(url)
    return redacted.split("://", 1)[-1].replace("***@", "") or "stream"


def _apply_ffmpeg_options(config):
    """Configure the FFmpeg backend before a capture is created.

    OpenCV reads OPENCV_FFMPEG_CAPTURE_OPTIONS only at VideoCapture
    construction, so this has to run immediately before every open rather than
    once at import.
    """
    transport = str(getattr(config, "RTSP_TRANSPORT", "tcp") or "tcp").lower()
    timeout_us = int(float(getattr(config, "RTSP_OPEN_TIMEOUT_MS", 8000)) * 1000)
    options = [
        f"rtsp_transport;{transport}",
        # FFmpeg renamed `stimeout` to `timeout` in 5.0. Sending both keeps old
        # and new builds working; the unrecognised one is ignored.
        f"stimeout;{timeout_us}",
        f"timeout;{timeout_us}",
    ]
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "|".join(options)


def _timeout_params(config):
    """Capture properties that bound how long an unreachable camera can block.

    These must be passed as VideoCapture params: FFmpeg's own stimeout/timeout
    options do not bound OpenCV's interrupt callback, which otherwise waits a
    fixed 30 seconds before conceding that a dead address is dead.
    """
    params = []
    wanted = (
        ("CAP_PROP_OPEN_TIMEOUT_MSEC", getattr(config, "RTSP_OPEN_TIMEOUT_MS", 8000)),
        ("CAP_PROP_READ_TIMEOUT_MSEC", getattr(config, "RTSP_READ_TIMEOUT_MS", 8000)),
    )
    for name, value in wanted:
        prop_id = getattr(cv2, name, None)
        if prop_id is not None and value:
            params += [int(prop_id), int(value)]
    return params


def open_capture(source, config=None):
    """Open a file path or a network stream and return the raw VideoCapture.

    The caller owns the handle and must release it.
    """
    if not is_stream_source(source):
        return cv2.VideoCapture(str(source))

    url = str(source).strip()
    params = []
    if config is not None:
        _apply_ffmpeg_options(config)
        params = _timeout_params(config)

    if params:
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG, params)
    else:
        # OpenCV builds older than 4.5.2 lack the params overload.
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)

    if cap.isOpened():
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, int(getattr(config, "RTSP_BUFFER_SIZE", 1)))
        except cv2.error:
            # Not every FFmpeg build honours this; a deeper buffer only costs
            # latency, so it is not worth failing the open over.
            logger.debug("Capture buffer size not supported by this backend")
    return cap


def probe_stream(source, config, warmup_frames=3):
    """Try to decode one frame. Returns (frame_or_None, reason).

    reason is "ok", "connect_failed", or "no_frames". The last two are worth
    telling apart: failing to connect points at the address, the network or a
    firewall, while connecting and getting no video points at the credentials,
    the channel, or an unsupported codec.

    The first frames off a fresh RTSP connection are usually the tail of the
    camera's GOP buffer and decode to grey mush, so a few are pulled and
    discarded before the one that gets returned.
    """
    cap = open_capture(source, config)
    try:
        if cap is None or not cap.isOpened():
            return None, "connect_failed"
        frame = None
        for _ in range(max(1, warmup_frames)):
            ok, candidate = cap.read()
            if ok and candidate is not None:
                frame = candidate
        return (frame, "ok") if frame is not None else (None, "no_frames")
    finally:
        if cap is not None:
            cap.release()


def grab_snapshot(source, config, warmup_frames=3):
    """Decode a single frame from a stream or file, or None if unavailable."""
    return probe_stream(source, config, warmup_frames)[0]


class VideoReader:
    def __init__(self, config):
        self.config = config

    def open(self, video_path):
        """Open a recorded file or a live camera URL."""
        if is_stream_source(video_path):
            return self.open_stream(video_path)
        return self.open_file(video_path)

    def open_file(self, video_path):
        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported format: {path.suffix}. "
                f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
            )

        cap = open_capture(path, self.config)
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
            "is_stream": False,
        }
        logger.info(f"Video opened: {path.name} ({width}x{height}, {fps:.2f} fps, {duration:.1f}s)")
        return cap, info

    def open_stream(self, url, name=None):
        """Open a live camera stream.

        A stream has no frame count and many Hikvision models report no FPS
        either, so both are filled with usable values instead of zero — the
        pipeline divides by FPS to build incident timestamps, and treats a
        total of zero as "unbounded" rather than "empty".

        The returned info carries only the redacted URL: it flows into job
        state and reports, neither of which may ever contain credentials.
        """
        safe_url = cfg.redact_rtsp_url(url)
        cap = open_capture(url, self.config)
        if cap is None or not cap.isOpened():
            if cap is not None:
                cap.release()
            raise RuntimeError(
                f"Could not open camera stream {safe_url}. Check that the IP address "
                f"is reachable, that RTSP is enabled on the camera, and that "
                f"RTSP_USERNAME / RTSP_PASSWORD in .env match the camera login."
            )

        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        if not 0 < fps < 240:
            fps = float(getattr(self.config, "RTSP_FALLBACK_FPS", 15.0))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

        info = {
            "path": safe_url,
            "name": name or stream_label(url),
            "fps": fps,
            "total_frames": 0,
            "width": width,
            "height": height,
            "duration": 0,
            "is_stream": True,
        }
        logger.info(f"Stream opened: {safe_url} ({width}x{height}, {fps:.2f} fps)")
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
