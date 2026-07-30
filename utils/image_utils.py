import cv2
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def save_violation_image(frame, bbox, track_id, config, video_name="unknown"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_video = Path(video_name).stem.replace(" ", "_")
    filename = f"violation_track{track_id}_{safe_video}_{timestamp}.jpg"
    save_path = config.IMAGES_DIR / filename

    x1, y1, x2, y2 = bbox
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(frame.shape[1], x2)
    y2 = min(frame.shape[0], y2)

    cropped = frame[y1:y2, x1:x2]
    if cropped.size == 0:
        logger.warning(f"Empty crop for Track ID {track_id}, saving full frame")
        cropped = frame

    annotated = frame.copy()
    color = (0, 0, 255)
    cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
    label = f"NO HELMET [ID: {track_id}]"
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    cv2.rectangle(annotated, (x1, y1 - th - 6), (x1 + tw + 6, y1), color, -1)
    cv2.putText(
        annotated, label, (x1 + 3, y1 - 3),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2,
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
