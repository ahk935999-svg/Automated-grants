from datetime import date, datetime

def _clamp(value):
    return max(0.0, min(100.0, float(value)))

def urgency_score(deadline):
    if not deadline:
        return 25.0
    try:
        days = (datetime.fromisoformat(deadline).date() - date.today()).days
    except ValueError:
        return 10.0
    if days < 0: return 0.0
    if days <= 3: return 100.0
    if days <= 7: return 90.0
    if days <= 14: return 75.0
    if days <= 30: return 55.0
    if days <= 60: return 35.0
    return 20.0

def funding_score(funding):
    if not funding:
        return 20.0
    text = funding.lower()
    if any(x in text for x in ("fully funded", "full funding", "tuition + stipend", "tuition and stipend")):
        return 100.0
    if any(x in text for x in ("tuition", "scholarship", "stipend")):
        return 70.0
    return 30.0

def profile_match(opportunity, profile):
    field = profile.get("education", {}).get("field", "").lower()
    haystack = f"{opportunity.title} {opportunity.summary}".lower()
    if field and field in haystack:
        return 100.0
    keywords = profile.get("preferences", {}).get("keywords", [])
    hits = sum(1 for k in keywords if k.lower() in haystack)
    return _clamp(35 + hits * 15)

def deterministic_evaluation(opportunity, profile):
    match = profile_match(opportunity, profile)
    funding = funding_score(opportunity.funding)
    urgency = urgency_score(opportunity.deadline)
    eligibility = 70.0 if profile.get("identity", {}).get("nationality") else 0.0
    competitiveness = 50.0
    confidence = 60.0
    overall = _clamp(
        eligibility * 0.30 + match * 0.25 + funding * 0.20 +
        urgency * 0.10 + competitiveness * 0.10 + confidence * 0.05
    )
    decision = "PRIORITY" if overall >= 70 else "REVIEW" if overall >= 45 else "LOW"
    return {
        "eligibility_score": eligibility,
        "profile_match_score": match,
        "funding_score": funding,
        "urgency_score": urgency,
        "competitiveness_score": competitiveness,
        "confidence_score": confidence,
        "overall_priority": overall,
        "decision": decision,
    }
