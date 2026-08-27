"""Non-Value-Added (NVA) activity analysis.

Answers three questions for a supervisor: what were people actually doing,
how much of that time added no value, and what should be changed first.
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

import config as cfg
from nva import (
    VALUE_CLASSES, build_breakdown, build_recommendations, catalog,
    format_duration,
)

from ..state import get_db

router = APIRouter(prefix="/api/nva", tags=["nva"])

RANGE_DAYS = {"7d": 7, "30d": 30, "90d": 90}


def _range(range_key, date_from, date_to):
    if date_from and date_to:
        return date_from, date_to
    days = RANGE_DAYS.get(range_key, 7)
    end = date.today()
    return (end - timedelta(days=days - 1)).isoformat(), end.isoformat()


def _fill_days(rows, start, end):
    """One point per day, so a quiet day reads as zero rather than vanishing."""
    by_date = {row["key"]: row for row in rows}
    cursor = date.fromisoformat(start)
    last = date.fromisoformat(end)
    series = []
    while cursor <= last:
        key = cursor.isoformat()
        row = by_date.get(key, {})
        va = round(float(row.get("va_seconds") or 0.0), 1)
        nnva = round(float(row.get("nnva_seconds") or 0.0), 1)
        nva = round(float(row.get("nva_seconds") or 0.0), 1)
        total = va + nnva + nva
        series.append({
            "date": key,
            "va_seconds": va,
            "nnva_seconds": nnva,
            "nva_seconds": nva,
            # `count` keeps the shape the shared trend chart already expects.
            "count": round(nva / 60.0, 1),
            "va_ratio": round((va / total) * 100, 1) if total > 0 else None,
        })
        cursor += timedelta(days=1)
    return series


def _thresholds():
    """The settings behind every label, so a number can always be traced."""
    return {
        "enabled": bool(getattr(cfg, "NVA_ENABLED", True)),
        "window_seconds": float(getattr(cfg, "NVA_WINDOW_SECONDS", 4.0)),
        "idle_speed": float(getattr(cfg, "NVA_IDLE_SPEED", 0.08)),
        "walk_speed": float(getattr(cfg, "NVA_WALK_SPEED", 0.35)),
        "search_straightness": float(getattr(cfg, "NVA_SEARCH_STRAIGHTNESS", 0.50)),
        "shuttle_reversals": int(getattr(cfg, "NVA_SHUTTLE_REVERSALS", 3)),
        "group_proximity": float(getattr(cfg, "NVA_GROUP_PROXIMITY", 2.5)),
        "idle_min_seconds": float(getattr(cfg, "NVA_IDLE_MIN_SECONDS", 8.0)),
        "min_segment_seconds": float(getattr(cfg, "NVA_MIN_SEGMENT_SECONDS", 3.0)),
        "target_va_ratio": float(getattr(cfg, "NVA_TARGET_VA_RATIO", 60.0)),
        "recommend_min_share": float(getattr(cfg, "NVA_RECOMMEND_MIN_SHARE", 2.0)),
    }


def _grouped(db, column, filters, limit=12):
    rows = db.nva_grouped(column, filters, limit=limit)
    result = []
    for row in rows:
        seconds = float(row.get("seconds") or 0.0)
        nva_seconds = float(row.get("nva_seconds") or 0.0)
        result.append({
            "key": row.get("key") or "",
            "seconds": round(seconds, 1),
            "nva_seconds": round(nva_seconds, 1),
            "va_seconds": round(float(row.get("va_seconds") or 0.0), 1),
            "duration": format_duration(nva_seconds),
            "occurrences": row.get("occurrences", 0),
            # Charted as minutes: seconds make every bar look identical.
            "count": round(nva_seconds / 60.0, 1),
            "nva_share": round((nva_seconds / seconds) * 100, 1) if seconds > 0 else 0.0,
        })
    return result


@router.get("/catalog")
def activity_catalog():
    """Every activity the system can recognise and how each one is classified.

    This is the reference an industrial engineer checks before trusting a
    number: which activities count as NVA, which waste they belong to, and the
    exact rule that produced the label.
    """
    return {
        "activities": catalog(),
        "value_classes": list(VALUE_CLASSES.values()),
        "thresholds": _thresholds(),
    }


@router.get("")
def nva_summary(
    range: str = Query("7d", pattern="^(7d|30d|90d|custom)$"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    camera_id: Optional[str] = None,
    location: Optional[str] = None,
):
    db = get_db()
    start, end = _range(range, date_from, date_to)
    filters = {
        "date_from": start,
        "date_to": end,
        "camera_id": camera_id,
        "location": location,
    }

    breakdown = build_breakdown(
        db.nva_by_activity(filters),
        observed_seconds=db.nva_observed_seconds(filters),
        tracks=db.nva_track_count(filters),
    )
    breakdown["recommendations"] = build_recommendations(breakdown, cfg)

    return {
        "range": {"from": start, "to": end, "key": range},
        "filters": {"camera_id": camera_id or "", "location": location or ""},
        "thresholds": _thresholds(),
        **breakdown,
        "trend": _fill_days(db.nva_daily(start, end, filters), start, end),
        "by_camera": _grouped(db, "camera_name", filters),
        "by_location": _grouped(db, "location", filters),
        "by_video": _grouped(db, "video_name", filters, limit=10),
        "recent_runs": db.get_analysis_runs(limit=10),
    }


@router.get("/activities")
def nva_activities(
    range: str = Query("7d", pattern="^(7d|30d|90d|custom)$"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    camera_id: Optional[str] = None,
    location: Optional[str] = None,
    activity: Optional[str] = None,
    value_class: Optional[str] = Query(None, pattern="^(VA|NNVA|NVA)$"),
    run_id: Optional[str] = None,
    min_duration: Optional[float] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    order_by: str = "duration_seconds",
    direction: str = Query("DESC", pattern="^(ASC|DESC|asc|desc)$"),
):
    """The individual segments behind the aggregates, longest first."""
    db = get_db()
    start, end = _range(range, date_from, date_to)
    filters = {
        "date_from": start,
        "date_to": end,
        "camera_id": camera_id,
        "location": location,
        "activity": activity,
        "value_class": value_class,
        "run_id": run_id,
        "min_duration": min_duration,
    }
    items = db.query_nva_activities(
        filters, limit=limit, offset=offset, order_by=order_by, direction=direction
    )
    for item in items:
        item["duration"] = format_duration(item.get("duration_seconds", 0))
    return {
        "items": items,
        "total": db.count_nva_activities(filters),
        "limit": limit,
        "offset": offset,
    }


@router.get("/runs/{run_id}")
def nva_for_run(run_id: str):
    """Value-stream breakdown for one analysis run or live session."""
    db = get_db()
    filters = {"run_id": run_id}
    rows = db.nva_by_activity(filters)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No activity recorded for run {run_id}")

    breakdown = build_breakdown(
        rows,
        observed_seconds=db.nva_observed_seconds(filters),
        tracks=db.nva_track_count(filters),
    )
    breakdown["recommendations"] = build_recommendations(breakdown, cfg)
    return {"run_id": run_id, "thresholds": _thresholds(), **breakdown}
