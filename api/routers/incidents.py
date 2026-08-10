"""Incident list, detail, review actions and the evidence gallery.

An incident is one confirmed violation for one tracked person — never one per
frame. The counts here are therefore directly comparable with the raw
detection totals shown on the analysis page.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..schemas import IncidentReview, serialize_incident
from ..state import get_db

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

REVIEW_STATUSES = {"Open", "Confirmed", "False Positive", "Resolved"}


def _filters(camera_id, location, status, violation_type, date_from, date_to,
             min_confidence, search, analysis_id):
    return {
        "camera_id": camera_id,
        "location": location,
        "status": status,
        "violation_type": violation_type,
        "date_from": date_from,
        "date_to": date_to,
        "min_confidence": min_confidence,
        "search": search,
        "analysis_id": analysis_id,
    }


@router.get("")
def list_incidents(
    camera_id: Optional[str] = None,
    location: Optional[str] = None,
    status: Optional[str] = None,
    violation_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    search: Optional[str] = None,
    analysis_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    order_by: str = "detected_at",
    direction: str = "DESC",
):
    db = get_db()
    filters = _filters(camera_id, location, status, violation_type,
                       date_from, date_to, min_confidence, search, analysis_id)
    rows = db.query_incidents(filters, limit=limit, offset=offset,
                              order_by=order_by, direction=direction)
    return {
        "items": [serialize_incident(r) for r in rows],
        "total": db.count_incidents(filters),
        "limit": limit,
        "offset": offset,
    }


@router.get("/filters")
def incident_filter_options():
    """Values actually present in the data, so filters can never be empty."""
    db = get_db()
    return {
        "cameras": db.distinct_values("camera_id"),
        "locations": db.distinct_values("location"),
        "statuses": sorted(REVIEW_STATUSES),
        "violation_types": db.distinct_values("violation_type"),
        "videos": db.distinct_values("video_name"),
    }


@router.get("/{incident_id}")
def get_incident(incident_id: str):
    db = get_db()
    rows = db.query_incidents({"search": incident_id}, limit=200)
    match = next((r for r in rows if r["incident_id"] == incident_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    incident = serialize_incident(match)
    # Everything else the same analysis produced, for context while reviewing.
    if incident["analysis_id"]:
        siblings = db.query_incidents({"analysis_id": incident["analysis_id"]}, limit=200)
        incident["related"] = [
            serialize_incident(r) for r in siblings if r["incident_id"] != incident_id
        ][:12]
    else:
        incident["related"] = []
    return incident


@router.patch("/{incident_id}")
def review_incident(incident_id: str, payload: IncidentReview):
    if payload.status not in REVIEW_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"status must be one of: {', '.join(sorted(REVIEW_STATUSES))}",
        )
    db = get_db()
    if db.fetch_by_id(incident_id) is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    db.review_incident(incident_id, payload.status, payload.reviewed_by, payload.remarks)
    return get_incident(incident_id)
