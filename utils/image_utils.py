import cv2
import logging
import numpy as np
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

HELMET_COLOR = (0, 255, 0)
VIOLATION_COLOR = (0, 0, 255)
UNKNOWN_COLOR = (128, 128, 128)
LABEL_BG = (255, 255, 255)
LABEL_TEXT = (0, 0, 0)


def annotate_frame(frame, persons_info, highlight_ids=()):
    annotated = frame.copy()
    highlight = set(highlight_ids)

    for p in persons_info:
        track_id = p["track_id"]
        x1, y1, x2, y2 = p["bbox"]
        has_helmet = bool(p.get("has_helmet", False))
        status = p.get("helmet_status")

        if status == "unknown":
            color = UNKNOWN_COLOR
            label = f"CHECKING [ID: {track_id}]"
            thickness = 1
        elif has_helmet:
            color = HELMET_COLOR
            label = f"HELMET [ID: {track_id}]"
            thickness = 1
        else:
            color = VIOLATION_COLOR
            label = f"NO HELMET [ID: {track_id}]"
            thickness = 3 if track_id in highlight else 1

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)

        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        top = y1 - th - 6 if y1 - th - 6 > 0 else y1 + 2
        cv2.rectangle(annotated, (x1, top), (x1 + tw + 6, top + th + 4), color, -1)
        cv2.putText(
            annotated, label, (x1 + 3, top + th + 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, LABEL_BG, 1,
        )

    return annotated


def save_violation_image(frame, persons_info, track_id, config, video_name="unknown",
                         video_time="00:00:00", reason=None, highlight_ids=None, title=None):
    safe_video = Path(video_name).stem.replace(" ", "_")
    safe_time = video_time.replace(":", "")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"violation_track{track_id}_{safe_video}_{safe_time}.jpg"
    save_path = config.IMAGES_DIR / filename

    highlight = list(highlight_ids) if highlight_ids else [track_id]
    annotated = annotate_frame(frame, persons_info, highlight_ids=highlight)

    with_helmet = sum(1 for p in persons_info if p.get("helmet_status") == "helmet")
    no_helmet = sum(1 for p in persons_info if p.get("helmet_status") == "no")
    scene_summary = (
        f"Persons in frame: {len(persons_info)} | "
        f"With helmet: {with_helmet} | Without helmet: {no_helmet}"
    )

    if title:
        header = title
    else:
        header = f"NO HELMET | Track {track_id} | Time {video_time}"
    if reason:
        reason = reason[:60]
        header = f"{header} | {reason}"
    (tw, th), _ = cv2.getTextSize(header, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    (sw, sh), _ = cv2.getTextSize(scene_summary, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    bg_w = max(tw, sw) + 16
    bg_h = th + sh + 20
    cv2.rectangle(annotated, (0, 0), (bg_w, bg_h), (0, 0, 0), -1)
    cv2.putText(
        annotated, header, (8, th + 4),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, VIOLATION_COLOR, 2,
    )
    cv2.putText(
        annotated, scene_summary, (8, th + sh + 16),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1,
    )

    success = cv2.imwrite(str(save_path), annotated, [
        cv2.IMWRITE_JPEG_QUALITY, config.IMAGE_QUALITY,
    ])
    if success:
        logger.info(f"Violation image saved: {save_path}")
        return str(save_path)
    else:
        logger.error(f"Failed to save image: {save_path}")
        return None


def generate_warning_poster(frame, persons_info, highlight_ids, config, video_name="unknown",
                            video_time="00:00:00", camera_name="", camera_id="", location="",
                            track_label="", confidence=0.0, reason=None):
    annotated = annotate_frame(frame, persons_info, highlight_ids=highlight_ids)
    ev_h, ev_w = annotated.shape[:2]

    width = max(960, ev_w)
    banner_h = 190
    scale = width / ev_w
    new_h = int(ev_h * scale)
    canvas_h = banner_h + new_h
    poster = np.full((canvas_h, width, 3), 240, dtype=np.uint8)

    cv2.rectangle(poster, (0, 0), (width, banner_h), (0, 0, 130), -1)
    cv2.rectangle(poster, (0, banner_h - 6), (width, banner_h), (0, 0, 0), -1)

    lines = [
        ("!! SAFETY VIOLATION - HELMET MISSING !!", 1.1, (255, 255, 255), 2),
        (f"Camera: {camera_name} ({camera_id})  |  Location: {location}", 0.7, (235, 235, 235), 1),
        (f"Video: {video_name}  |  Time: {video_time}", 0.7, (235, 235, 235), 1),
        (f"Track(s): {track_label}  |  Confidence: {confidence:.2f}", 0.7, (235, 235, 235), 1),
    ]
    if reason:
        lines.append((f"Reason: {reason[:90]}", 0.7, (235, 235, 235), 1))

    y = 30
    for text, font_scale, color, thickness in lines:
        cv2.putText(poster, text, (20, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
        y += 34

    scaled = cv2.resize(annotated, (width, new_h), interpolation=cv2.INTER_AREA)
    poster[banner_h:banner_h + new_h, 0:width] = scaled

    safe_video = Path(video_name).stem.replace(" ", "_")
    safe_time = video_time.replace(":", "")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"warning_poster_{track_label}_{safe_video}_{safe_time}_{timestamp}.jpg"
    save_path = config.WARNING_POSTERS_DIR / filename

    success = cv2.imwrite(str(save_path), poster, [
        cv2.IMWRITE_JPEG_QUALITY, config.IMAGE_QUALITY,
    ])
    if success:
        logger.info(f"Warning poster saved: {save_path}")
        return str(save_path)
    logger.error(f"Failed to save poster: {save_path}")
    return None
