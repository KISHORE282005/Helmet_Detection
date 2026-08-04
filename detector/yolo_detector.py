import cv2
import numpy as np
import logging
from pathlib import Path

from ultralytics import YOLO

logger = logging.getLogger(__name__)


class YOLODetector:
    def __init__(self, config):
        self.config = config
        self.person_model = None
        self.helmet_model = None
        self._load_models()

    def _load_models(self):
        person_path = str(self.config.PERSON_MODEL_PATH)
        if Path(person_path).exists():
            self.person_model = YOLO(person_path)
            logger.info(f"Loaded person model: {person_path}")
        else:
            logger.info("Downloading YOLOv11n person model...")
            self.person_model = YOLO("yolo11n.pt")
            logger.info("Person model loaded")

        helmet_path = str(self.config.HELMET_MODEL_PATH)
        if Path(helmet_path).exists():
            self.helmet_model = YOLO(helmet_path)
            logger.info(f"Loaded helmet model: {helmet_path}")
        else:
            logger.warning(
                f"Helmet model not found at {helmet_path}. "
                "Using head-region analysis fallback. "
                "For production, train a custom helmet detection model."
            )
            self.helmet_model = None

    def detect(self, frame):
        persons = self._detect_persons(frame)
        for person in persons:
            analysis = self._check_helmet(frame, person["bbox"])
            person["has_helmet"] = analysis["has_helmet"]
            person["helmet_analysis"] = analysis
        return persons

    def _detect_persons(self, frame):
        results = self.person_model(
            frame,
            classes=[self.config.PERSON_CLASS_ID],
            conf=self.config.CONFIDENCE_THRESHOLD,
            verbose=False,
        )
        detections = []
        if len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confs = results[0].boxes.conf.cpu().numpy()
            for box, conf in zip(boxes, confs):
                x1, y1, x2, y2 = map(int, box)
                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "confidence": float(conf),
                    "class_id": self.config.PERSON_CLASS_ID,
                    "has_helmet": False,
                })
        return detections

    def _check_helmet(self, frame, bbox):
        if self.helmet_model is not None:
            return self._check_helmet_model(frame, bbox)
        return self._check_helmet_heuristic(frame, bbox)

    def _head_roi(self, frame, bbox):
        x1, y1, x2, y2 = bbox
        h = y2 - y1
        w = x2 - x1
        top = max(0, y1 - int(0.02 * h))
        bottom = min(frame.shape[0], y1 + int(0.38 * h))
        left = max(0, x1 + int(0.10 * w))
        right = min(frame.shape[1], x2 - int(0.10 * w))
        if left >= right:
            left, right = x1, x2
        return frame[top:bottom, left:right], (top, bottom, left, right)

    def _validate_head(self, frame, bbox):
        """Return (valid, reason, head_roi). Rejects heads that are too small,
        cropped by the frame edge, blurred, occluded, or poorly lit so that a
        single unreliable frame can never drive a violation decision."""
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = bbox
        bh = y2 - y1
        bw = x2 - x1
        if bh <= 0 or bw <= 0:
            return False, "empty person bbox", None

        head_roi, (top, bottom, left, right) = self._head_roi(frame, bbox)
        if head_roi.size == 0 or bottom <= top or right <= left:
            return False, "no head region", None

        hh = bottom - top
        hw = right - left
        if min(hh, hw) < self.config.MIN_HEAD_SIZE:
            return False, f"head too small ({hh}x{hw}px)", head_roi

        # Detect how much of the intended head region is clipped by the frame
        # edge (the 10% side margins and 2% top offset are normal, not crops).
        top_intended = y1 - int(0.02 * bh)
        bottom_intended = y1 + int(0.38 * bh)
        crop_top = max(0, -top_intended) / max(1, hh)
        crop_bottom = max(0, bottom_intended - h) / max(1, hh)
        crop_left = max(0, -left) / max(1, hw)
        crop_right = max(0, right - w) / max(1, hw)
        crop = max(crop_top, crop_bottom, crop_left, crop_right)
        if crop > self.config.MAX_HEAD_EDGE_OVERLAP:
            return False, "head partially outside frame", head_roi

        gray = cv2.cvtColor(head_roi, cv2.COLOR_BGR2GRAY)
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        if sharpness < self.config.MIN_HEAD_SHARPNESS:
            return False, f"motion blur/out of focus (sharpness {sharpness:.0f})", head_roi

        hsv = cv2.cvtColor(head_roi, cv2.COLOR_BGR2HSV)
        v = hsv[:, :, 2]
        brightness = float(v.mean())
        if brightness < self.config.MIN_HEAD_BRIGHTNESS:
            return False, f"too dark (brightness {brightness:.0f})", head_roi
        if brightness > self.config.MAX_HEAD_BRIGHTNESS:
            return False, f"overexposed (brightness {brightness:.0f})", head_roi
        contrast = float(v.std())
        if contrast < self.config.MIN_HEAD_CONTRAST:
            return False, f"severe occlusion/low contrast (std {contrast:.0f})", head_roi

        return True, "ok", head_roi

    def _invalid_analysis(self, reason):
        return {
            "has_helmet": False, "confidence": 0.0,
            "reason": f"head invalid: {reason}", "ratios": {},
            "head_valid": False, "head_reason": reason,
        }

    def _check_helmet_model(self, frame, bbox):
        valid, reason, head_roi = self._validate_head(frame, bbox)
        if not valid:
            return self._invalid_analysis(reason)

        results = self.helmet_model(head_roi, conf=self.config.CONFIDENCE_THRESHOLD, verbose=False)
        if len(results) > 0 and results[0].boxes is not None and len(results[0].boxes) > 0:
            confidence = float(results[0].boxes.conf.max())
            return {
                "has_helmet": True, "confidence": confidence,
                "reason": f"helmet model confidence {confidence:.2f}", "ratios": {},
                "head_valid": True, "head_reason": "ok",
            }
        return {
            "has_helmet": False, "confidence": 0.0,
            "reason": "helmet model found nothing", "ratios": {},
            "head_valid": True, "head_reason": "ok",
        }

    def _skin_mask(self, hsv):
        """True where pixels look like human skin. Skin is excluded from helmet
        matching so a bare head (skin/hair/forehead) can never be misread as a
        helmet, no matter how warm the lighting."""
        skin = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for lower, upper in self.config.SKIN_COLOR_RANGES:
            skin = cv2.bitwise_or(
                skin,
                cv2.inRange(
                    hsv,
                    np.array(lower, dtype=np.uint8),
                    np.array(upper, dtype=np.uint8),
                ),
            )
        return skin

    def _check_helmet_heuristic(self, frame, bbox):
        valid, reason, head_roi = self._validate_head(frame, bbox)
        if not valid:
            return self._invalid_analysis(reason)

        hh, hw = head_roi.shape[:2]
        hsv = cv2.cvtColor(head_roi, cv2.COLOR_BGR2HSV)
        skin = self._skin_mask(hsv)

        # Match only the CROWN: the top half of the head region, central 60%
        # of its width. That is where a helmet crown sits; the lower head and
        # side fringes (hair, ears, forehead) are excluded.
        cr_rows = max(1, int(hh * 0.5))
        cl = max(0, int(hw * 0.2))
        cr = max(cl + 1, int(hw * 0.8))
        crown_hsv = hsv[:cr_rows, cl:cr]
        crown_skin = skin[:cr_rows, cl:cr]
        total = crown_hsv.shape[0] * crown_hsv.shape[1]

        combined = np.zeros(crown_hsv.shape[:2], dtype=np.uint8)
        ratios = {}
        for name, lower, upper in self.config.HELMET_COLOR_RANGES:
            mask = cv2.inRange(
                crown_hsv,
                np.array(lower, dtype=np.uint8),
                np.array(upper, dtype=np.uint8),
            )
            mask = cv2.bitwise_and(mask, cv2.bitwise_not(crown_skin))
            ratios[name] = float(np.count_nonzero(mask)) / total
            combined = cv2.bitwise_or(combined, mask)

        ratio = float(np.count_nonzero(combined)) / total

        if ratio >= self.config.HELMET_MIN_RATIO:
            has_helmet = True
            confidence = min(0.99, 0.55 + ratio)
            reason = f"helmet crown covers {ratio:.0%} of head"
        else:
            has_helmet = False
            missing = max(0.0, self.config.HELMET_MIN_RATIO - ratio)
            confidence = min(0.99, 0.80 + missing)
            reason = f"no helmet (bare head, helmet color {ratio:.0%} of crown)"

        return {
            "has_helmet": has_helmet,
            "confidence": confidence,
            "reason": reason,
            "ratios": ratios,
            "head_valid": True, "head_reason": "ok",
        }
