"""The activity catalogue — what the system can observe, and which of those
observations count as Non-Value-Added (NVA) work.

Terminology follows lean manufacturing, where every minute an operator spends
falls into exactly one of three buckets:

  VA    Value-Added         the customer pays for it — the part changes shape,
                            fit or function while the operator is doing it.
  NNVA  Necessary NVA       the customer does not pay for it, but today's
                            process cannot run without it (walking to fetch a
                            part, moving material). Minimise, do not delete.
  NVA   Non-Value-Added     pure waste. Delete it.

A fixed overhead camera plus person tracking can only see *where a body is and
how it moves*, so this catalogue is deliberately limited to the wastes that
leave a motion signature. Wastes such as Inventory, Overproduction and Defects
are real, but they are not visible in a person's trajectory and are therefore
not claimed here.

`DETECTION` on each entry states the exact rule that produced the label, so an
industrial engineer can audit any minute the dashboard charged to waste.
"""

# Value classes
VA = "VA"
NNVA = "NNVA"
NVA = "NVA"

VALUE_CLASSES = {
    VA: {
        "key": VA,
        "label": "Value-Added",
        "description": "Work the customer pays for — the product is being changed.",
        "tone": "good",
    },
    NNVA: {
        "key": NNVA,
        "label": "Necessary NVA",
        "description": (
            "Required by the current process but adds no value. Minimise it by "
            "redesigning the layout or the flow."
        ),
        "tone": "warning",
    },
    NVA: {
        "key": NVA,
        "label": "Non-Value-Added",
        "description": "Pure waste. Eliminate the cause, not the symptom.",
        "tone": "critical",
    },
}

# Lean waste categories (TIMWOODS) that a camera can actually evidence.
WASTE_WAITING = "Waiting"
WASTE_MOTION = "Motion"
WASTE_TRANSPORT = "Transport"

# ---------------------------------------------------------------------------
# The activity catalogue
# ---------------------------------------------------------------------------
# `min_seconds` is the shortest run of an activity that is worth recording. A
# two-second pause is normal work rhythm, not waiting, so short runs are never
# charged to waste.
ACTIVITIES = {
    "working": {
        "key": "working",
        "label": "Active work at station",
        "value_class": VA,
        "waste": None,
        "description": (
            "The operator is at a fixed position with continuous body movement "
            "and no travel — the motion signature of hands-on work."
        ),
        "detection": (
            "Movement present but below the travel threshold, and net "
            "displacement stays under one body-height across the window."
        ),
        "min_seconds": 3.0,
    },
    "walking": {
        "key": "walking",
        "label": "Walking / material movement",
        "value_class": NNVA,
        "waste": WASTE_TRANSPORT,
        "description": (
            "Purposeful travel between two points. Necessary in today's layout, "
            "but every metre walked is a metre not spent adding value."
        ),
        "detection": (
            "Sustained directed travel: speed above the walk threshold with a "
            "straight path (net displacement close to path length)."
        ),
        "min_seconds": 3.0,
    },
    "idle": {
        "key": "idle",
        "label": "Idle / standing still",
        "value_class": NVA,
        "waste": WASTE_WAITING,
        "description": (
            "The operator is present but stationary — waiting on a machine "
            "cycle, a part, an instruction, or a colleague."
        ),
        "detection": (
            "Near-zero movement for longer than the idle threshold, with no "
            "other stationary person nearby."
        ),
        "min_seconds": 8.0,
    },
    "waiting_group": {
        "key": "waiting_group",
        "label": "Group huddle / unplanned discussion",
        "value_class": NVA,
        "waste": WASTE_WAITING,
        "description": (
            "Two or more people stationary together. Either an unplanned "
            "discussion, or several operators blocked by the same problem — "
            "the second case multiplies the cost of one stoppage."
        ),
        "detection": (
            "Two or more tracks simultaneously stationary within the proximity "
            "radius of each other."
        ),
        "min_seconds": 6.0,
    },
    "searching": {
        "key": "searching",
        "label": "Searching / excess motion",
        "value_class": NVA,
        "waste": WASTE_MOTION,
        "description": (
            "A lot of movement that goes nowhere — hunting for a tool, a "
            "fixture, a document or a part."
        ),
        "detection": (
            "High travelled distance with low net displacement (a wandering, "
            "low-straightness path)."
        ),
        "min_seconds": 4.0,
    },
    "shuttling": {
        "key": "shuttling",
        "label": "Repeated back-and-forth trips",
        "value_class": NVA,
        "waste": WASTE_TRANSPORT,
        "description": (
            "The same short trip made over and over — the classic signature of "
            "a badly placed bin, tool or machine."
        ),
        "detection": (
            "Several direction reversals inside one window while the person "
            "ends up close to where they started."
        ),
        "min_seconds": 5.0,
    },
    "unknown": {
        "key": "unknown",
        "label": "Not yet classified",
        "value_class": None,
        "waste": None,
        "description": (
            "The track is too new or too short-lived to have a reliable motion "
            "history. Never charged to value or to waste."
        ),
        "detection": "Observed for less than the minimum track history.",
        "min_seconds": 0.0,
    },
}

#: Activities that are charged to waste, ordered by how expensive they usually
#: are to leave alone. Used to break ties when two wastes score the same.
NVA_ACTIVITIES = ("idle", "waiting_group", "shuttling", "searching")

#: Activities that consume operator time and therefore count toward the
#: denominator of the value-added ratio.
MEASURED_ACTIVITIES = ("working", "walking") + NVA_ACTIVITIES


def activity(key):
    """Catalogue entry for `key`, falling back to the 'unknown' entry."""
    return ACTIVITIES.get(key, ACTIVITIES["unknown"])


def value_class_of(key):
    return activity(key)["value_class"]


def waste_of(key):
    return activity(key)["waste"]


def is_nva(key):
    return value_class_of(key) == NVA


def catalog():
    """The catalogue as a serialisable list, ordered VA → NNVA → NVA.

    This is what the dashboard renders to answer "which activities count as
    NVA, and why" without the operator having to read the source.
    """
    order = {VA: 0, NNVA: 1, NVA: 2, None: 3}
    entries = sorted(
        ACTIVITIES.values(),
        key=lambda a: (order[a["value_class"]], a["key"]),
    )
    return [dict(entry) for entry in entries]
