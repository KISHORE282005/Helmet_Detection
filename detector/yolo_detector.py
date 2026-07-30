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
            person["has_helmet"] = self._check_helmet(frame, person["bbox"])
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

    def _check_helmet_model(self, frame, bbox):
        x1, y1, x2, y2 = bbox
        head_y2 = y1 + int((y2 - y1) * 0.35)
        head_x1 = max(0, x1 - int((x2 - x1) * 0.1))
        head_x2 = min(frame.shape[1], x2 + int((x2 - x1) * 0.1))
        head_y1 = max(0, y1 - int((y2 - y1) * 0.05))
        head_y2 = min(frame.shape[0], head_y2)

        head_roi = frame[head_y1:head_y2, head_x1:head_x2]
        if head_roi.size == 0:
            return False

        results = self.helmet_model(head_roi, conf=self.config.CONFIDENCE_THRESHOLD, verbose=False)
        if len(results) > 0 and results[0].boxes is not None:
            return len(results[0].boxes) > 0
        return False

    def _check_helmet_heuristic(self, frame, bbox):
        x1, y1, x2, y2 = bbox
        head_y2 = y1 + int((y2 - y1) * 0.30)
        head_roi = frame[y1:head_y2, x1:x2]
        if head_roi.size == 0:
            return False

        hsv = cv2.cvtColor(head_roi, cv2.COLOR_BGR2HSV)
        saturation = np.mean(hsv[:, :, 1])
        value = np.mean(hsv[:, :, 2])

        lower_yellow = np.array([20, 80, 150])
        upper_yellow = np.array([35, 255, 255])
        lower_white = np.array([0, 0, 180])
        upper_white = np.array([180, 40, 255])
        lower_blue = np.array([100, 80, 80])
        upper_blue = np.array([130, 255, 255])
        lower_orange = np.array([5, 100, 150])
        upper_orange = np.array([15, 255, 255])

        mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)
        mask_white = cv2.inRange(hsv, lower_white, upper_white)
        mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)
        mask_orange = cv2.inRange(hsv, lower_orange, upper_orange)

        combined_mask = mask_yellow | mask_white | mask_blue | mask_orange
        helmet_pixel_ratio = np.sum(combined_mask > 0) / combined_mask.size

        return helmet_pixel_ratio > 0.15 or saturation > 50
