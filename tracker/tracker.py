import numpy as np
import logging
from collections import defaultdict

from boxmot.trackers.bbox.bytetrack import ByteTrack

logger = logging.getLogger(__name__)


class PersonTracker:
    def __init__(self, config):
        self.config = config
        self.tracker = ByteTrack(
            track_thresh=config.CONFIDENCE_THRESHOLD,
            track_buffer=config.MAX_TRACK_AGE,
            match_thresh=0.8,
            frame_rate=30,
            min_conf=config.CONFIDENCE_THRESHOLD * 0.8,
        )
        self.captured_ids = set()
        self.track_history = defaultdict(list)
        self.frame_count = 0

    def update(self, person_detections, frame):
        self.frame_count += 1
        if not person_detections:
            self.tracker.update(np.empty((0, 6)), np.zeros((10, 10, 3), dtype=np.uint8))
            return []

        dets = np.array([
            [d["bbox"][0], d["bbox"][1], d["bbox"][2], d["bbox"][3],
             d["confidence"], float(d["class_id"])]
            for d in person_detections
        ])

        tracked = self.tracker.update(dets, frame)
        results = []

        for t in tracked:
            track_id = int(t[4])
            x1, y1, x2, y2 = map(int, t[0:4])

            match = None
            for pd in person_detections:
                pb = pd["bbox"]
                iou = self._compute_iou([x1, y1, x2, y2], pb)
                if iou > 0.5:
                    match = pd
                    break

            results.append({
                "track_id": track_id,
                "bbox": [x1, y1, x2, y2],
                "confidence": float(t[5]) if len(t) > 5 else (match["confidence"] if match else 0.0),
                "has_helmet": match["has_helmet"] if match else False,
                "is_new_capture": track_id not in self.captured_ids,
            })

        return results

    def mark_captured(self, track_id):
        self.captured_ids.add(track_id)
        logger.info(f"Track ID {track_id} marked as captured")

    def was_captured(self, track_id):
        return track_id in self.captured_ids

    def _compute_iou(self, box1, box2):
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        if x1 >= x2 or y1 >= y2:
            return 0.0

        inter = (x2 - x1) * (y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - inter

        return inter / union if union > 0 else 0.0

    def reset(self):
        self.captured_ids.clear()
        self.track_history.clear()
        self.frame_count = 0
        logger.info("Tracker reset")
