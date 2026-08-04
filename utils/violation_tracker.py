import cv2
import logging
from collections import deque

logger = logging.getLogger(__name__)

SHARPNESS_MAX = 5000.0


def frame_sharpness(roi):
    if roi is None or roi.size == 0:
        return 0.0
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def average_roi_sharpness(frame, bboxes):
    vals = []
    for b in bboxes:
        x1, y1, x2, y2 = map(int, b)
        roi = frame[y1:y2, x1:x2]
        if roi.size:
            vals.append(min(frame_sharpness(roi), SHARPNESS_MAX) / SHARPNESS_MAX)
    return sum(vals) / len(vals) if vals else 0.0


class TrackState:
    """Per-person history maintained across the whole video."""

    __slots__ = (
        "track_id", "history", "consecutive_no", "consecutive_helmet",
        "confidence_sum", "confidence_count", "best", "first_seen_frame",
        "last_seen_frame", "last_seen_time", "confirmed", "status",
    )

    def __init__(self, track_id, history_size, first_seen_frame):
        self.track_id = track_id
        self.history = deque(maxlen=history_size)
        self.consecutive_no = 0
        self.consecutive_helmet = 0
        self.confidence_sum = 0.0
        self.confidence_count = 0
        self.best = None
        self.first_seen_frame = first_seen_frame
        self.last_seen_frame = first_seen_frame
        self.last_seen_time = None
        self.confirmed = False
        self.status = "monitoring"


class EvidenceCandidate:
    """Best buffered evidence frame for a confirming no-helmet run."""

    __slots__ = (
        "track_id", "frame", "bbox", "confidence",
        "frame_index", "video_time", "persons_info", "reason",
    )

    def __init__(self, track_id, frame, bbox, confidence, frame_index, video_time,
                 persons_info, reason):
        self.track_id = track_id
        self.frame = frame
        self.bbox = bbox
        self.confidence = confidence
        self.frame_index = frame_index
        self.video_time = video_time
        self.persons_info = persons_info
        self.reason = reason


class ViolationEvent:
    """Emitted when a no-helmet violation is temporally confirmed."""

    __slots__ = ("track_id", "candidate", "confidence")

    def __init__(self, track_id, candidate, confidence):
        self.track_id = track_id
        self.candidate = candidate
        self.confidence = confidence


class ViolationTracker:
    """Temporal verification for helmet violations.

    Never confirms a violation from a single frame. Each tracked person must
    show "No Helmet" for VIOLATION_REQUIRED_FRAMES consecutive valid frames.
    Any helmet frame, low-confidence frame, or invalid head region resets (or
    pauses) the consecutive counter so false positives are suppressed.
    """

    def __init__(self, config):
        self.config = config
        self.required_frames = int(getattr(config, "VIOLATION_REQUIRED_FRAMES", 30))
        self.confidence_threshold = float(getattr(config, "HELMET_CONFIDENCE_THRESHOLD", 0.90))
        self.person_conf_threshold = float(getattr(config, "CONFIDENCE_THRESHOLD", 0.60))
        self.gap_reset = int(getattr(config, "CONSECUTIVE_GAP_RESET", 5))
        self.history_size = int(getattr(config, "TRACK_HISTORY_SIZE", 60))
        self.ttl = int(getattr(config, "MAX_TRACK_AGE", 60)) + 30
        self.states = {}

    def update(self, tracked_persons, frame, frame_index, video_time):
        """Process one analyzed frame. Returns a list of ViolationEvents."""
        events = []
        seen = set()

        persons_info = [
            {
                "track_id": p["track_id"],
                "bbox": list(p["bbox"]),
                "has_helmet": bool(p["has_helmet"]),
                "helmet_status": self._status_of(p),
                "confidence": float(p["confidence"]),
            }
            for p in tracked_persons
        ]

        for p in tracked_persons:
            track_id = p["track_id"]
            seen.add(track_id)

            state = self.states.get(track_id)
            if state is None:
                state = TrackState(track_id, self.history_size, frame_index)
                self.states[track_id] = state
            if state.confirmed:
                continue

            if frame_index - state.last_seen_frame > self.gap_reset:
                self._reset_counters(state, "track reappeared after a gap")

            state.last_seen_frame = frame_index
            state.last_seen_time = video_time

            analysis = p.get("helmet_analysis") or {}
            if not analysis.get("head_valid", True):
                state.history.append("invalid")
                logger.debug(
                    f"Track {track_id} frame {frame_index}: {analysis.get('head_reason')} -> ignored"
                )
                continue

            if float(p["confidence"]) < self.person_conf_threshold:
                state.history.append("invalid")
                continue

            confidence = float(analysis.get("confidence", 0.0))
            if confidence < self.confidence_threshold:
                state.history.append("uncertain")
                logger.debug(
                    f"Track {track_id} frame {frame_index}: confidence {confidence:.2f} "
                    f"< {self.confidence_threshold} -> ignored"
                )
                continue

            if bool(p["has_helmet"]):
                state.consecutive_helmet += 1
                self._reset_counters(state, "helmet seen -> violation counter reset")
                state.history.append("helmet")
                continue

            state.consecutive_no += 1
            state.confidence_sum += confidence
            state.confidence_count += 1
            state.history.append("no")
            state.status = "counting"

            candidate = EvidenceCandidate(
                track_id, frame.copy(), list(p["bbox"]), confidence,
                frame_index, video_time,
                list(persons_info), analysis.get("reason", "no helmet"),
            )
            if state.best is None or self._score(candidate) > self._score(state.best):
                state.best = candidate

            if state.consecutive_no >= self.required_frames:
                avg_conf = state.confidence_sum / max(1, state.confidence_count)
                events.append(ViolationEvent(track_id, state.best, avg_conf))
                state.confirmed = True
                state.status = "confirmed"
                logger.info(
                    f"CONFIRMED | Track {track_id} no helmet for {state.consecutive_no} "
                    f"consecutive frames | avg conf {avg_conf:.2f} | frame {frame_index}"
                )

        for track_id in list(self.states):
            if frame_index - self.states[track_id].last_seen_frame > self.ttl:
                logger.debug(f"Track {track_id} state removed after timeout")
                del self.states[track_id]

        return events

    @staticmethod
    def _status_of(p):
        analysis = p.get("helmet_analysis") or {}
        if not analysis.get("head_valid", True):
            return "unknown"
        return "helmet" if p["has_helmet"] else "no"

    def _reset_counters(self, state, reason):
        if state.consecutive_no > 0 or state.confidence_count > 0:
            logger.debug(
                f"Track {state.track_id}: {reason} (had {state.consecutive_no} consecutive no-helmet)"
            )
        state.consecutive_no = 0
        state.consecutive_helmet = 0
        state.confidence_sum = 0.0
        state.confidence_count = 0
        state.best = None
        state.status = "monitoring"

    def _score(self, candidate):
        x1, y1, x2, y2 = candidate.bbox
        fh, fw = candidate.frame.shape[:2]
        area_ratio = max(0, (x2 - x1) * (y2 - y1)) / max(1, fw * fh)
        sharpness = min(
            frame_sharpness(candidate.frame[y1:y2, x1:x2]), SHARPNESS_MAX
        ) / SHARPNESS_MAX
        return 0.40 * area_ratio + 0.25 * sharpness + 0.35 * candidate.confidence

    def reset(self):
        self.states.clear()
        logger.info("Violation tracker reset")
