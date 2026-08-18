"""Motion-signature activity recognition for NVA analysis.

The tracker turns each person's trajectory into a timeline of named activities
(`working`, `walking`, `idle`, ...) which the catalogue then charges to VA,
NNVA or NVA. It reuses the ByteTrack IDs the safety pipeline already produces,
so it costs a few floating-point operations per person per frame and no extra
inference.

Three design rules, inherited from the helmet verifier:

1. **No single frame decides anything.** Every label comes from a rolling
   window of trajectory, and a label must hold for a minimum duration before it
   is recorded as a segment. A two-second pause is work rhythm, not waiting.
2. **Everything is scale-normalised.** Distances are divided by the person's
   own bounding-box height, so "how fast is this person moving" means the same
   thing for someone near the camera and someone at the far end of the bay.
   Thresholds are in body-heights per second and need no per-camera tuning.
3. **Jitter is never mistaken for motion.** Path length is measured between
   half-second waypoints rather than between consecutive frames, so a
   stationary person's box jitter cannot accumulate into a walking speed.
"""

import logging
import statistics
from collections import Counter, deque

from .catalog import (
    MEASURED_ACTIVITIES, NNVA, NVA, VA, activity, value_class_of, waste_of,
)

logger = logging.getLogger(__name__)


class ActivitySegment:
    """One continuous run of a single activity by one tracked person."""

    __slots__ = (
        "track_id", "activity", "value_class", "waste", "start_seconds",
        "end_seconds", "start_time", "end_time", "confidence", "avg_speed",
        "net_displacement",
    )

    def __init__(self, track_id, activity_key, start_seconds, start_time):
        self.track_id = track_id
        self.activity = activity_key
        self.value_class = value_class_of(activity_key)
        self.waste = waste_of(activity_key)
        self.start_seconds = start_seconds
        self.end_seconds = start_seconds
        self.start_time = start_time
        self.end_time = start_time
        self.confidence = 0.0
        self.avg_speed = 0.0
        self.net_displacement = 0.0

    @property
    def duration_seconds(self):
        return max(0.0, self.end_seconds - self.start_seconds)

    def to_dict(self):
        return {
            "track_id": self.track_id,
            "activity": self.activity,
            "label": activity(self.activity)["label"],
            "value_class": self.value_class,
            "waste": self.waste,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "start_seconds": round(self.start_seconds, 2),
            "end_seconds": round(self.end_seconds, 2),
            "duration_seconds": round(self.duration_seconds, 2),
            "confidence": round(self.confidence, 3),
            "avg_speed": round(self.avg_speed, 3),
            "net_displacement": round(self.net_displacement, 3),
        }


class _TrackState:
    """Rolling trajectory and the segment currently being accumulated."""

    __slots__ = (
        "track_id", "points", "raw_labels", "current", "segment",
        "matching_frames", "total_frames", "speed_sum", "speed_count",
        "net_sum", "last_seconds", "first_seconds",
    )

    def __init__(self, track_id, seconds, smoothing_frames):
        self.track_id = track_id
        self.points = deque()
        self.raw_labels = deque(maxlen=max(1, smoothing_frames))
        self.current = None
        self.segment = None
        self.matching_frames = 0
        self.total_frames = 0
        self.speed_sum = 0.0
        self.speed_count = 0
        self.net_sum = 0.0
        self.last_seconds = seconds
        self.first_seconds = seconds


class ActivityTracker:
    """Classifies what every tracked person is doing, second by second.

    Feed it the same `tracked_persons` list the helmet pipeline already builds.
    `update()` returns the segments that closed on this frame; `finalize()`
    closes whatever is still open when the video (or the live session) ends.
    """

    def __init__(self, config):
        self.config = config
        self.enabled = bool(getattr(config, "NVA_ENABLED", True))
        self.window = float(getattr(config, "NVA_WINDOW_SECONDS", 4.0))
        self.sample = max(0.05, float(getattr(config, "NVA_SAMPLE_SECONDS", 0.5)))
        self.smoothing = float(getattr(config, "NVA_SMOOTHING_SECONDS", 1.5))
        self.idle_speed = float(getattr(config, "NVA_IDLE_SPEED", 0.08))
        self.walk_speed = float(getattr(config, "NVA_WALK_SPEED", 0.35))
        self.travel_net = float(getattr(config, "NVA_TRAVEL_NET", 1.20))
        self.search_straightness = float(getattr(config, "NVA_SEARCH_STRAIGHTNESS", 0.50))
        self.shuttle_window = float(getattr(config, "NVA_SHUTTLE_WINDOW_SECONDS", 12.0))
        self.shuttle_reversals = int(getattr(config, "NVA_SHUTTLE_REVERSALS", 3))
        self.shuttle_min_path = float(getattr(config, "NVA_SHUTTLE_MIN_PATH", 4.0))
        self.shuttle_straightness = float(getattr(config, "NVA_SHUTTLE_STRAIGHTNESS", 0.35))
        # Trajectory kept in memory: enough for whichever window reaches back
        # furthest.
        self.history_seconds = max(self.window, self.shuttle_window)
        self.reversal_min_step = float(getattr(config, "NVA_REVERSAL_MIN_STEP", 0.25))
        self.group_proximity = float(getattr(config, "NVA_GROUP_PROXIMITY", 2.5))
        self.group_min_people = int(getattr(config, "NVA_GROUP_MIN_PEOPLE", 2))
        self.min_track_seconds = float(getattr(config, "NVA_MIN_TRACK_SECONDS", 2.0))
        self.gap_reset = float(getattr(config, "NVA_GAP_RESET_SECONDS", 3.0))

        # Per-activity minimum durations: catalogue defaults, with the two an
        # operator is most likely to want to tune exposed through config.
        self.min_seconds = {
            key: float(entry["min_seconds"]) for key, entry in
            ((k, activity(k)) for k in MEASURED_ACTIVITIES)
        }
        self.min_seconds["idle"] = float(
            getattr(config, "NVA_IDLE_MIN_SECONDS", self.min_seconds["idle"])
        )
        default_min = getattr(config, "NVA_MIN_SEGMENT_SECONDS", None)
        if default_min is not None:
            for key in ("working", "walking", "searching", "shuttling"):
                self.min_seconds[key] = float(default_min)

        self.states = {}
        self.segments = []
        self.observed_seconds = 0.0
        self.tracks_seen = set()
        # Running per-class totals so a UI can show the split mid-run without
        # re-summing every segment on each progress tick.
        self.class_seconds = {VA: 0.0, NNVA: 0.0, NVA: 0.0}
        self._last_seconds = None

    # ------------------------------------------------------------------
    # Per-frame entry point
    # ------------------------------------------------------------------
    def update(self, tracked_persons, video_time, time_seconds):
        """Process one analyzed frame.

        `time_seconds` is the position on the source clock — the offset into a
        recording, or elapsed wall-clock time on a live feed — so segment
        durations stay true regardless of how fast the pipeline runs.

        Returns the ActivitySegments that closed on this frame.
        """
        if not self.enabled:
            return []

        # Order matters: the smoothing width is derived from the gap since the
        # previous frame, which _accumulate_observed_time is about to consume.
        smoothing_frames = self._smoothing_frames(time_seconds)
        self._accumulate_observed_time(len(tracked_persons), time_seconds)

        measurements = {}

        for person in tracked_persons:
            track_id = person["track_id"]
            self.tracks_seen.add(track_id)
            state = self.states.get(track_id)
            if state is None:
                state = _TrackState(track_id, time_seconds, smoothing_frames)
                self.states[track_id] = state
            elif time_seconds - state.last_seconds > self.gap_reset:
                # The person was out of view long enough that the trajectory
                # either side cannot be treated as one movement.
                self._close_segment(state, state.last_seconds)
                state.points.clear()
                state.raw_labels.clear()
                state.first_seconds = time_seconds

            state.last_seconds = time_seconds
            self._append_point(state, person["bbox"], time_seconds)
            measurements[track_id] = self._measure(state, time_seconds)

        labels = {
            track_id: self._classify(metrics)
            for track_id, metrics in measurements.items()
        }
        self._apply_group_rule(tracked_persons, measurements, labels)

        closed = []
        for track_id, raw_label in labels.items():
            state = self.states[track_id]
            state.raw_labels.append(raw_label)
            metrics = measurements[track_id]
            if metrics["speed"] is not None:
                state.speed_sum += metrics["speed"]
                state.net_sum += metrics["net"]
                state.speed_count += 1

            stable = self._stable_label(state)
            if stable is None:
                continue
            if stable != state.current:
                segment = self._close_segment(state, time_seconds)
                if segment:
                    closed.append(segment)
                self._open_segment(state, stable, time_seconds, video_time)
            else:
                state.segment.end_seconds = time_seconds
                state.segment.end_time = video_time

            state.total_frames += 1
            if raw_label == stable:
                state.matching_frames += 1

        self._prune(time_seconds)
        return closed

    def finalize(self, time_seconds):
        """Close every open segment at the end of the run."""
        if not self.enabled:
            return []
        closed = []
        for state in self.states.values():
            segment = self._close_segment(state, min(time_seconds, state.last_seconds))
            if segment:
                closed.append(segment)
        return closed

    # ------------------------------------------------------------------
    # Trajectory maths
    # ------------------------------------------------------------------
    def _append_point(self, state, bbox, seconds):
        x1, y1, x2, y2 = bbox
        height = max(1.0, float(y2 - y1))
        state.points.append((seconds, (x1 + x2) / 2.0, (y1 + y2) / 2.0, height))
        cutoff = seconds - self.history_seconds
        while state.points and state.points[0][0] < cutoff:
            state.points.popleft()

    def _measure(self, state, seconds):
        """Scale-normalised motion metrics for one person.

        Two horizons are measured. The short one (`NVA_WINDOW_SECONDS`) decides
        what the person is doing right now — speed, net displacement,
        straightness. The long one (`NVA_SHUTTLE_WINDOW_SECONDS`) exists only
        to recognise repeated trips, because whether a single round trip
        happens to fall inside a four-second window is an accident of timing.

        Speed is in body-heights per second; distances in body-heights;
        straightness runs 0 (wandering) to 1 (a straight line).
        """
        empty = {
            "speed": None, "net": 0.0, "path": 0.0, "straightness": 0.0,
            "reversals": 0, "long_path": 0.0, "long_straightness": 0.0,
            "long_reversals": 0, "long_span": 0.0,
            "centroid": None, "height": 0.0, "span": 0.0,
        }
        points = list(state.points)
        if len(points) < 2:
            return empty

        height = statistics.median(p[3] for p in points)
        centroid = (points[-1][1], points[-1][2])
        recent = [p for p in points if p[0] >= seconds - self.window]
        span = (recent[-1][0] - recent[0][0]) if len(recent) >= 2 else 0.0
        empty.update({"centroid": centroid, "height": height, "span": span})

        # A brand-new track has no history to judge; saying "unknown" is
        # honest, guessing from a fraction of a second is not.
        if span < min(self.min_track_seconds, self.window) or height <= 0:
            return empty

        short = self._window_metrics(recent, height)
        if short is None:
            return empty
        long = self._window_metrics(points, height) or short

        return {
            "speed": short["path"] / span if span > 0 else 0.0,
            "net": short["net"],
            "path": short["path"],
            "straightness": short["straightness"],
            "reversals": short["reversals"],
            "long_path": long["path"],
            "long_straightness": long["straightness"],
            "long_reversals": long["reversals"],
            "long_span": points[-1][0] - points[0][0],
            "centroid": centroid,
            "height": height,
            "span": span,
        }

    def _window_metrics(self, points, height):
        """Travelled distance, net displacement, straightness and reversals."""
        waypoints = self._waypoints(points)
        if len(waypoints) < 2:
            return None
        steps = [
            (waypoints[i + 1][0] - waypoints[i][0], waypoints[i + 1][1] - waypoints[i][1])
            for i in range(len(waypoints) - 1)
        ]
        path = sum(self._norm(step) for step in steps) / height
        net = self._norm((
            waypoints[-1][0] - waypoints[0][0],
            waypoints[-1][1] - waypoints[0][1],
        )) / height
        return {
            "path": path,
            "net": net,
            "straightness": (net / path) if path > 1e-6 else 0.0,
            "reversals": self._count_reversals(steps, height),
        }

    def _waypoints(self, points):
        """Average the trajectory into half-second waypoints.

        Measuring between waypoints rather than between frames is what stops
        bounding-box jitter — a couple of pixels each frame — from summing into
        a walking speed for someone who never moved.
        """
        buckets = {}
        start = points[0][0]
        for seconds, cx, cy, _ in points:
            index = int((seconds - start) / self.sample)
            total_x, total_y, count = buckets.get(index, (0.0, 0.0, 0))
            buckets[index] = (total_x + cx, total_y + cy, count + 1)
        return [
            (buckets[i][0] / buckets[i][2], buckets[i][1] / buckets[i][2])
            for i in sorted(buckets)
        ]

    def _count_reversals(self, steps, height):
        """Direction changes sharper than 120 degrees between real movements."""
        floor = self.reversal_min_step * height
        significant = [s for s in steps if self._norm(s) >= floor]
        reversals = 0
        for first, second in zip(significant, significant[1:]):
            magnitude = self._norm(first) * self._norm(second)
            if magnitude <= 0:
                continue
            cosine = (first[0] * second[0] + first[1] * second[1]) / magnitude
            if cosine < -0.5:
                reversals += 1
        return reversals

    @staticmethod
    def _norm(vector):
        return (vector[0] ** 2 + vector[1] ** 2) ** 0.5

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------
    def _classify(self, metrics):
        speed = metrics["speed"]
        if speed is None:
            return "unknown"
        if speed < self.idle_speed:
            return "idle"

        # Tested before the travel gate below: a shuttle ends where it started,
        # so its net displacement is small by definition and it would never
        # register as travel. What identifies it is ground covered over the
        # long horizon plus sharp reversals with almost nothing to show for it.
        if (metrics["long_span"] >= self.shuttle_window * 0.6
                and metrics["long_reversals"] >= self.shuttle_reversals
                and metrics["long_path"] >= self.shuttle_min_path
                and metrics["long_straightness"] < self.shuttle_straightness):
            return "shuttling"

        travelling = speed >= self.walk_speed or metrics["net"] >= self.travel_net
        if not travelling:
            # Movement without travel: the operator is working at a station.
            return "working"
        if metrics["straightness"] < self.search_straightness:
            return "searching"
        return "walking"

    def _apply_group_rule(self, tracked_persons, measurements, labels):
        """Promote co-located idle people to a group huddle.

        One person standing still is waiting. Three standing still together is
        a different problem with a different fix, so it gets its own activity.
        """
        idle = [
            track_id for track_id, label in labels.items()
            if label == "idle" and measurements[track_id]["centroid"]
        ]
        if len(idle) < self.group_min_people:
            return

        for track_id in idle:
            metrics = measurements[track_id]
            cx, cy = metrics["centroid"]
            radius = self.group_proximity * metrics["height"]
            companions = 0
            for other in idle:
                if other == track_id:
                    continue
                ox, oy = measurements[other]["centroid"]
                if self._norm((cx - ox, cy - oy)) <= radius:
                    companions += 1
            if companions >= self.group_min_people - 1:
                labels[track_id] = "waiting_group"

    def _stable_label(self, state):
        """Majority label across the smoothing window.

        A single misclassified frame — a person half-occluded by a forklift,
        say — must not be able to open a segment on its own.
        """
        if not state.raw_labels:
            return None
        # Opening the first segment needs at least half a smoothing window of
        # evidence; once a segment is open, one frame can extend it.
        if state.current is None and len(state.raw_labels) < max(2, state.raw_labels.maxlen // 2):
            return None
        label, count = Counter(state.raw_labels).most_common(1)[0]
        if count * 2 <= len(state.raw_labels):
            return state.current  # no majority — hold the current label
        return label

    def _smoothing_frames(self, time_seconds):
        """Convert the smoothing window from seconds to analyzed frames."""
        if self._last_seconds is None:
            return 5
        step = time_seconds - self._last_seconds
        if step <= 0:
            return 5
        return max(2, int(round(self.smoothing / step)))

    # ------------------------------------------------------------------
    # Segment bookkeeping
    # ------------------------------------------------------------------
    def _open_segment(self, state, activity_key, seconds, video_time):
        state.current = activity_key
        state.segment = ActivitySegment(state.track_id, activity_key, seconds, video_time)
        state.matching_frames = 0
        state.total_frames = 0
        state.speed_sum = 0.0
        state.net_sum = 0.0
        state.speed_count = 0

    def _close_segment(self, state, seconds):
        """Finish the open segment, keeping it only if it ran long enough."""
        segment = state.segment
        state.segment = None
        state.current = None
        if segment is None:
            return None

        segment.end_seconds = max(segment.end_seconds, seconds)
        segment.confidence = (
            state.matching_frames / state.total_frames if state.total_frames else 0.0
        )
        if state.speed_count:
            segment.avg_speed = state.speed_sum / state.speed_count
            segment.net_displacement = state.net_sum / state.speed_count

        minimum = self.min_seconds.get(segment.activity)
        if minimum is None or segment.duration_seconds < minimum:
            # Too short to be a real activity — the time still counts toward
            # observed person-time, it is simply not charged to value or waste.
            return None

        self.segments.append(segment)
        if segment.value_class in self.class_seconds:
            self.class_seconds[segment.value_class] += segment.duration_seconds
        logger.debug(
            f"ACTIVITY | Track {segment.track_id} | {segment.activity} | "
            f"{segment.start_time}-{segment.end_time} | "
            f"{segment.duration_seconds:.1f}s | conf {segment.confidence:.2f}"
        )
        return segment

    def _accumulate_observed_time(self, person_count, time_seconds):
        if self._last_seconds is not None:
            step = time_seconds - self._last_seconds
            # A large step means a reconnect or a seek, not elapsed floor time.
            if 0 < step <= self.gap_reset:
                self.observed_seconds += person_count * step
        self._last_seconds = time_seconds

    def _prune(self, time_seconds):
        for track_id in [
            tid for tid, state in self.states.items()
            if time_seconds - state.last_seconds > self.gap_reset * 3
        ]:
            self._close_segment(self.states[track_id], self.states[track_id].last_seconds)
            del self.states[track_id]

    def live_totals(self):
        """Cheap mid-run snapshot for progress reporting."""
        classified = sum(self.class_seconds.values())
        return {
            "observed_seconds": round(self.observed_seconds, 1),
            "classified_seconds": round(classified, 1),
            "va_seconds": round(self.class_seconds[VA], 1),
            "nnva_seconds": round(self.class_seconds[NNVA], 1),
            "nva_seconds": round(self.class_seconds[NVA], 1),
            "nva_share": (
                round((self.class_seconds[NVA] / classified) * 100, 1)
                if classified > 0 else None
            ),
            "va_share": (
                round((self.class_seconds[VA] / classified) * 100, 1)
                if classified > 0 else None
            ),
            "segments": len(self.segments),
        }

    def reset(self):
        self.states.clear()
        self.segments.clear()
        self.tracks_seen.clear()
        self.observed_seconds = 0.0
        self.class_seconds = {VA: 0.0, NNVA: 0.0, NVA: 0.0}
        self._last_seconds = None
