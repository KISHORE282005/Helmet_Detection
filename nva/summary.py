"""Aggregation of activity segments into a value-stream breakdown.

One shape is produced here and consumed everywhere — the pipeline summary at
the end of a run, the Excel report, and the dashboard API — so the numbers an
operator sees on screen are the same numbers the recommender reasoned about.
"""

from .catalog import (
    MEASURED_ACTIVITIES, NNVA, NVA, VA, VALUE_CLASSES, activity,
    value_class_of, waste_of,
)


def format_duration(seconds):
    """Human-readable duration: 2h 05m, 7m 30s, 42s."""
    seconds = max(0, int(round(float(seconds or 0))))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def build_breakdown(rows, observed_seconds=0.0, tracks=0):
    """Turn per-activity totals into the full value-stream breakdown.

    `rows` is any iterable of dicts with `activity`, `seconds` and
    `occurrences` — segments summed in memory at the end of a run, or the
    result of a GROUP BY over the stored activities. Anything not in the
    catalogue's measured set is dropped rather than silently counted.

    Shares are taken over *classified* time, not observed time: a person whose
    activity could not be determined is excluded from both numerator and
    denominator instead of being quietly charged to value.
    """
    totals = {}
    for row in rows:
        key = row.get("activity")
        if key not in MEASURED_ACTIVITIES:
            continue
        entry = totals.setdefault(key, {"seconds": 0.0, "occurrences": 0})
        entry["seconds"] += float(row.get("seconds") or 0.0)
        entry["occurrences"] += int(row.get("occurrences") or 0)

    classified = sum(entry["seconds"] for entry in totals.values())
    share = (lambda value: round((value / classified) * 100, 1)) if classified > 0 else (lambda _: 0.0)

    by_activity = []
    for key in MEASURED_ACTIVITIES:
        entry = totals.get(key)
        if not entry or entry["seconds"] <= 0:
            continue
        meta = activity(key)
        by_activity.append({
            "activity": key,
            "label": meta["label"],
            "value_class": meta["value_class"],
            "waste": meta["waste"],
            "description": meta["description"],
            "seconds": round(entry["seconds"], 1),
            "duration": format_duration(entry["seconds"]),
            "occurrences": entry["occurrences"],
            "avg_seconds": round(entry["seconds"] / entry["occurrences"], 1)
            if entry["occurrences"] else 0.0,
            "share": share(entry["seconds"]),
        })
    by_activity.sort(key=lambda row: row["seconds"], reverse=True)

    value_split = []
    for value_class in (VA, NNVA, NVA):
        seconds = sum(
            entry["seconds"] for key, entry in totals.items()
            if value_class_of(key) == value_class
        )
        meta = VALUE_CLASSES[value_class]
        value_split.append({
            "value_class": value_class,
            "label": meta["label"],
            "description": meta["description"],
            "tone": meta["tone"],
            "seconds": round(seconds, 1),
            "duration": format_duration(seconds),
            "share": share(seconds),
        })

    waste_totals = {}
    for key, entry in totals.items():
        waste = waste_of(key)
        if not waste:
            continue
        bucket = waste_totals.setdefault(waste, {"seconds": 0.0, "occurrences": 0, "activities": []})
        bucket["seconds"] += entry["seconds"]
        bucket["occurrences"] += entry["occurrences"]
        bucket["activities"].append(activity(key)["label"])

    by_waste = sorted(
        (
            {
                "waste": waste,
                "seconds": round(bucket["seconds"], 1),
                "duration": format_duration(bucket["seconds"]),
                "occurrences": bucket["occurrences"],
                "share": share(bucket["seconds"]),
                "activities": sorted(bucket["activities"]),
            }
            for waste, bucket in waste_totals.items()
        ),
        key=lambda row: row["seconds"],
        reverse=True,
    )

    lookup = {row["value_class"]: row for row in value_split}
    return {
        "observed_seconds": round(float(observed_seconds or 0.0), 1),
        "observed_duration": format_duration(observed_seconds),
        "classified_seconds": round(classified, 1),
        "classified_duration": format_duration(classified),
        "tracks": int(tracks or 0),
        # None rather than 0 when nothing was classified: an empty analysis has
        # no value-added ratio, and printing 0% would read as a failing line.
        "va_ratio": lookup[VA]["share"] if classified > 0 else None,
        "nnva_ratio": lookup[NNVA]["share"] if classified > 0 else None,
        "nva_ratio": lookup[NVA]["share"] if classified > 0 else None,
        "nva_seconds": lookup[NVA]["seconds"],
        "va_seconds": lookup[VA]["seconds"],
        "nnva_seconds": lookup[NNVA]["seconds"],
        "value_split": value_split,
        "by_activity": by_activity,
        "by_waste": by_waste,
    }


def summarize(segments, observed_seconds=0.0, tracks=0):
    """Breakdown for a finished run, from its ActivitySegment objects."""
    rows = [
        {"activity": segment.activity, "seconds": segment.duration_seconds, "occurrences": 1}
        for segment in segments
    ]
    return build_breakdown(rows, observed_seconds=observed_seconds, tracks=tracks)
