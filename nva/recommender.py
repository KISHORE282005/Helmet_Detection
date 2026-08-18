"""Turns a value-stream breakdown into ranked improvement actions.

Every recommendation is traceable: it names the activity that triggered it, the
lean waste it belongs to, how much time was actually measured, and what to do
about it. Nothing is emitted without measured time behind it — a recommendation
the numbers do not support is worse than no recommendation at all.

The playbook is standard industrial-engineering practice (line balancing, 5S,
spaghetti diagrams, SMED, point-of-use storage). It is intentionally editable:
a plant that knows its own failure modes should extend `PLAYBOOK` rather than
work around it.
"""

from .catalog import NVA_ACTIVITIES, activity
from .summary import format_duration

HIGH = "high"
MEDIUM = "medium"
LOW = "low"

PLAYBOOK = {
    "idle": {
        "title": "Cut operator waiting time",
        "root_causes": [
            "Unbalanced line — one station finishes well before the next is ready",
            "Machine cycle the operator watches instead of leaving to run",
            "Material or instruction arriving late at the station",
            "Approval, inspection or changeover the operator cannot start alone",
        ],
        "actions": [
            "Build a Yamazumi (stacked cycle-time) chart per station and rebalance work to takt.",
            "Separate machine time from operator time so the operator loads and walks away instead of watching the cycle.",
            "Trigger replenishment with a kanban or a two-bin system so parts arrive before the station runs dry.",
            "Fit an andon signal so a stoppage is escalated in seconds rather than absorbed as standing time.",
        ],
        "lean_tool": "Line balancing / Yamazumi · Standard Work · Andon",
        "expected_impact": "Waiting is the cheapest waste to remove — rebalancing typically recovers most of it without capital spend.",
        "verify": "Re-run this analysis after the change; idle share should fall while value-added share rises.",
    },
    "waiting_group": {
        "title": "Break up unplanned huddles at the line",
        "root_causes": [
            "One stoppage blocking several operators at once",
            "Problem-solving happening at the machine instead of at a scheduled tier meeting",
            "Missing standard work, so operators confer about how to proceed",
            "Shift handover or briefing taking place on the line",
        ],
        "actions": [
            "Escalate stoppages through an andon so one problem stops one person, not a group.",
            "Move discussion into a short structured tier meeting at a fixed time and board.",
            "Publish standard work at the station so the method does not need to be debated.",
            "Check the staffing plan: recurring huddles at the same station usually mean it is over-manned.",
        ],
        "lean_tool": "Andon · Tiered daily management · Standard Work",
        "expected_impact": "Removes the multiplier effect where a single stoppage costs several operators at once.",
        "verify": "Group-huddle time should collapse into either productive work or a single, shorter idle segment.",
    },
    "searching": {
        "title": "Stop operators hunting for tools and parts",
        "root_causes": [
            "No fixed home position for tools, fixtures or consumables",
            "Shared tooling stored away from the point of use",
            "Unlabelled or over-full storage that has to be searched",
            "Missing paperwork, drawings or job cards at the station",
        ],
        "actions": [
            "Run 5S on the station: a marked, shadowed home for every tool, and nothing else on the bench.",
            "Move high-frequency items to point-of-use storage within arm's reach.",
            "Give shared tooling a signed-out home location so a missing tool is visible immediately.",
            "Put the job card, drawing and gauges in one kit issued with the work order.",
        ],
        "lean_tool": "5S · Point-of-use storage · Visual management",
        "expected_impact": "Searching is almost entirely recoverable — it disappears once every item has one obvious home.",
        "verify": "Re-run the analysis after 5S; searching segments should nearly vanish at the improved station.",
    },
    "shuttling": {
        "title": "Eliminate repeated back-and-forth trips",
        "root_causes": [
            "Materials, bins or scrap containers placed outside the work envelope",
            "One shared machine, gauge or printer serving stations that are far from it",
            "Batch handling — carrying one part at a time instead of a full load",
            "Work sequence that crosses the cell twice per part",
        ],
        "actions": [
            "Draw a spaghetti diagram of the trip and relocate whatever is at the far end of it.",
            "Bring bins, gauges and scrap containers inside the operator's work envelope.",
            "Resequence standard work so each cell crossing does several jobs at once.",
            "Where the trip is unavoidable, hand it to a timed water-spider route instead of the operator.",
        ],
        "lean_tool": "Spaghetti diagram · Cell layout redesign · Water spider route",
        "expected_impact": "Repeated short trips are usually one badly placed item; the fix is layout, not effort.",
        "verify": "Track the same station after the move — shuttling should convert into working time.",
    },
}

# Applies to Necessary-NVA rather than pure waste: walking has to happen, but
# an unusual share of it points at layout.
WALKING_PLAYBOOK = {
    "title": "Shorten the walking distance built into the layout",
    "root_causes": [
        "Stations, stores and inspection points spread over a large footprint",
        "Material delivered to a central point rather than to the line",
        "Cell layout that does not follow the process sequence",
    ],
    "actions": [
        "Map the route with a spaghetti diagram and re-lay the cell in process sequence (U-shape where possible).",
        "Deliver material to the point of use on a timed route instead of having operators fetch it.",
        "Co-locate the gauges and paperwork each station needs with that station.",
    ],
    "lean_tool": "Spaghetti diagram · Cell layout · Plan for Every Part",
    "expected_impact": "Walking cannot be removed entirely, but layout work routinely halves it.",
    "verify": "Compare walking share before and after the layout change on the same camera.",
}


def _severity(share, config):
    high = float(getattr(config, "NVA_SEVERITY_HIGH_SHARE", 15.0))
    medium = float(getattr(config, "NVA_SEVERITY_MEDIUM_SHARE", 7.0))
    if share >= high:
        return HIGH
    if share >= medium:
        return MEDIUM
    return LOW


def build_recommendations(breakdown, config=None, limit=8):
    """Ranked improvement actions for a value-stream breakdown.

    Only activities that hold at least `NVA_RECOMMEND_MIN_SHARE` percent of
    classified time produce a recommendation, so a handful of stray seconds
    never turns into a work order.
    """
    config = config or object()
    min_share = float(getattr(config, "NVA_RECOMMEND_MIN_SHARE", 2.0))
    target_va = float(getattr(config, "NVA_TARGET_VA_RATIO", 60.0))

    rows = {row["activity"]: row for row in breakdown.get("by_activity", [])}
    if not rows or not breakdown.get("classified_seconds"):
        return []

    recommendations = []

    # Headline: the value-added ratio itself, when it sits below target.
    va_ratio = breakdown.get("va_ratio")
    if va_ratio is not None and va_ratio < target_va:
        nva_ratio = breakdown.get("nva_ratio") or 0.0
        recommendations.append({
            "id": "nva-value-ratio",
            "activity": None,
            "title": f"Value-added ratio is {va_ratio:.1f}% against a {target_va:.0f}% target",
            "waste": None,
            "severity": HIGH if va_ratio < target_va * 0.6 else MEDIUM,
            "share": va_ratio,
            "seconds": breakdown.get("va_seconds", 0.0),
            "occurrences": 0,
            "observation": (
                f"Of {breakdown['classified_duration']} of classified operator time, "
                f"{format_duration(breakdown.get('va_seconds', 0))} was value-added and "
                f"{format_duration(breakdown.get('nva_seconds', 0))} "
                f"({nva_ratio:.1f}%) was non-value-added."
            ),
            "root_causes": [
                "Waste is distributed across several activities rather than one obvious cause",
                "Standard work either missing or not followed at the observed stations",
            ],
            "actions": [
                "Work the specific wastes listed below in order — they are ranked by measured time.",
                "Set a value-added ratio target per cell and review it at the daily tier meeting.",
                "Re-run this analysis on the same camera after each change so the effect is measured, not assumed.",
            ],
            "lean_tool": "Value stream mapping · Standard Work",
            "expected_impact": (
                f"Closing the gap to {target_va:.0f}% would convert about "
                f"{format_duration(max(0.0, (target_va - va_ratio) / 100 * breakdown['classified_seconds']))} "
                f"of the observed period into productive work."
            ),
            "verify": "Re-run the analysis on comparable footage and compare the value-added ratio.",
        })

    # One recommendation per NVA activity with enough measured time.
    for key in NVA_ACTIVITIES:
        row = rows.get(key)
        if not row or row["share"] < min_share:
            continue
        play = PLAYBOOK[key]
        meta = activity(key)
        recommendations.append({
            "id": f"nva-{key}",
            "activity": key,
            "title": play["title"],
            "waste": meta["waste"],
            "severity": _severity(row["share"], config),
            "share": row["share"],
            "seconds": row["seconds"],
            "occurrences": row["occurrences"],
            "observation": (
                f"{meta['label']} accounted for {row['share']:.1f}% of classified operator "
                f"time ({row['duration']} across {row['occurrences']} "
                f"occurrence{'s' if row['occurrences'] != 1 else ''}, "
                f"averaging {format_duration(row['avg_seconds'])} each)."
            ),
            "root_causes": list(play["root_causes"]),
            "actions": list(play["actions"]),
            "lean_tool": play["lean_tool"],
            "expected_impact": play["expected_impact"],
            "verify": play["verify"],
        })

    # Walking is necessary, so it is only raised when it is disproportionate.
    walking = rows.get("walking")
    walking_trigger = float(getattr(config, "NVA_WALKING_ALERT_SHARE", 20.0))
    if walking and walking["share"] >= walking_trigger:
        recommendations.append({
            "id": "nva-walking",
            "activity": "walking",
            "title": WALKING_PLAYBOOK["title"],
            "waste": activity("walking")["waste"],
            "severity": _severity(walking["share"], config),
            "share": walking["share"],
            "seconds": walking["seconds"],
            "occurrences": walking["occurrences"],
            "observation": (
                f"Walking took {walking['share']:.1f}% of classified operator time "
                f"({walking['duration']}). It is necessary in the current layout, but at "
                f"this share the layout itself is the constraint."
            ),
            "root_causes": list(WALKING_PLAYBOOK["root_causes"]),
            "actions": list(WALKING_PLAYBOOK["actions"]),
            "lean_tool": WALKING_PLAYBOOK["lean_tool"],
            "expected_impact": WALKING_PLAYBOOK["expected_impact"],
            "verify": WALKING_PLAYBOOK["verify"],
        })

    rank = {HIGH: 0, MEDIUM: 1, LOW: 2}
    recommendations.sort(key=lambda r: (rank[r["severity"]], -r["seconds"]))
    return recommendations[:limit]
