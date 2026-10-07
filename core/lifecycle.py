STATES=(
    "DISCOVERED","VERIFIED","ELIGIBLE","PREPARING","READY",
    "SUBMITTING","SUBMITTED","ACKNOWLEDGED","INTERVIEW","DECISION",
    "ACCEPTED","REJECTED","WAITLISTED","INTERVENTION",
)

TRANSITIONS={
    "DISCOVERED":{"VERIFIED","REJECTED","INTERVENTION"},
    "VERIFIED":{"ELIGIBLE","REJECTED","INTERVENTION"},
    "ELIGIBLE":{"PREPARING","REJECTED","INTERVENTION"},
    "PREPARING":{"READY","INTERVENTION"},
    "READY":{"SUBMITTING","INTERVENTION"},
    "SUBMITTING":{"SUBMITTED","INTERVENTION"},
    "SUBMITTED":{"ACKNOWLEDGED","DECISION"},
    "ACKNOWLEDGED":{"INTERVIEW","DECISION"},
    "INTERVIEW":{"DECISION"},
    "DECISION":{"ACCEPTED","REJECTED","WAITLISTED"},
    "INTERVENTION":{"PREPARING","READY","SUBMITTING"},
    "ACCEPTED":set(),
    "REJECTED":set(),
    "WAITLISTED":{"DECISION"},
}

def can_transition(current,target):
    return current==target or target in TRANSITIONS.get(current,set())

def transition(current,target):
    if not can_transition(current,target):
        raise ValueError(f"Invalid application transition: {current} -> {target}")
    return target
