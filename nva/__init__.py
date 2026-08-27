"""NVA (Non-Value-Added) activity analysis.

Reads the person trajectories the safety pipeline already produces, names what
each person is doing, charges that time to Value-Added / Necessary-NVA / NVA,
and recommends the lean countermeasure for whatever is costing the most.

    from nva import ActivityTracker, summarize, build_recommendations

    tracker = ActivityTracker(config)
    for frame in video:
        tracker.update(tracked_persons, video_time, time_seconds)
    tracker.finalize(time_seconds)

    breakdown = summarize(tracker.segments, tracker.observed_seconds)
    actions = build_recommendations(breakdown, config)
"""

from .activity_tracker import ActivitySegment, ActivityTracker
from .catalog import (
    ACTIVITIES, MEASURED_ACTIVITIES, NNVA, NVA, NVA_ACTIVITIES, VA,
    VALUE_CLASSES, activity, catalog, is_nva, value_class_of, waste_of,
)
from .recommender import build_recommendations
from .summary import build_breakdown, format_duration, summarize

__all__ = [
    "ACTIVITIES", "MEASURED_ACTIVITIES", "NVA_ACTIVITIES", "VALUE_CLASSES",
    "VA", "NNVA", "NVA",
    "ActivitySegment", "ActivityTracker",
    "activity", "build_breakdown", "build_recommendations", "catalog",
    "format_duration", "is_nva", "summarize", "value_class_of", "waste_of",
]
