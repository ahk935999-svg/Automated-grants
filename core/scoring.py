from datetime import date, datetime
import re

def clamp(value):
    return max(0.0, min(100.0, float(value)))

def infer_funding(text):
    lowered = text.lower()
    if any(x in lowered for x in ("fully funded", "fully-funded", "full scholarship", "tuition + stipend", "tuition and stipend")):
        return "fully funded"
    if any(x in lowered for x in ("scholarship", "stipend", "tuition waiver", "tuition-free")):
        return "scholarship/partial or full"
    return None

def infer_deadline(text):
    patterns = (
        r"\b(20\d{2})-(0?[1-9]|1[0-2])-([0-3]?\d)\b",
        r"\b([0-3]?\d)[ /.-](0?[1-9]|1[0-2])[ /.-](20\d{2})\b"
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        groups = match.groups()
        if len(groups) == 3 and len(groups[0]) == 4:
            return f"{int(groups[0]):04d}-{int(groups[1]):02d}-{int(groups[2]):02d}"
        return f"{int(groups[2]):04d}-{int(groups[1]):02d}-{int(groups[0]):02d}"
    return None

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
    if not funding: return 20.0
    text = funding.lower()
    if "fully funded" in text or "full scholarship" in text: return 100.0
    if any(x in text for x in ("scholarship", "stipend", "tuition")): return 70.0
    return 30.0

def profile_match(opportunity, profile):
    field = profile.get("education", {}).get("field", "").lower()
    haystack = f"{opportunity.title} {opportunity.summary}".lower()
    if field and field in haystack: return 100.0
    hits = sum(1 for k in profile.get("preferences", {}).get("keywords", []) if k.lower() in haystack)
    return clamp(35 + hits * 15)

def deterministic_evaluation(opportunity, profile, eligibility):
    match = profile_match(opportunity, profile)
    funding = funding_score(opportunity.funding)
    urgency = urgency_score(opportunity.deadline)
    eligibility_score = eligibility.score
    competitiveness = 50.0
    confidence = 60.0
    overall = clamp(
        eligibility_score * 0.30 + match * 0.25 + funding * 0.20 +
        urgency * 0.10 + competitiveness * 0.10 + confidence * 0.05
    )
    if eligibility.status == "INELIGIBLE":
        decision = "LOW"
    else:
        decision = "PRIORITY" if overall >= 70 else "REVIEW" if overall >= 45 else "LOW"
    return {
        "eligibility_score": eligibility_score,
        "profile_match_score": match,
        "funding_score": funding,
        "urgency_score": urgency,
        "competitiveness_score": competitiveness,
        "confidence_score": confidence,
        "overall_priority": overall,
        "decision": decision,
        "reasons": eligibility.reasons + eligibility.blockers,
    }

def merge_ai_scores(base, ai, eligibility_status, verification_status):
    if not ai:
        return base
    merged = dict(base)
    for key in ("profile_match_score", "funding_score", "urgency_score", "competitiveness_score", "confidence_score"):
        if key in ai and isinstance(ai[key], (int, float)):
            merged[key] = clamp(ai[key])
    merged["eligibility_score"] = base["eligibility_score"]
    merged["overall_priority"] = clamp(
        merged["eligibility_score"] * 0.30 +
        merged["profile_match_score"] * 0.25 +
        merged["funding_score"] * 0.20 +
        merged["urgency_score"] * 0.10 +
        merged["competitiveness_score"] * 0.10 +
        merged["confidence_score"] * 0.05
    )
    if eligibility_status == "INELIGIBLE":
        merged["decision"] = "LOW"
        merged["overall_priority"] = min(merged["overall_priority"], 10.0)
    else:
        merged["decision"] = "PRIORITY" if merged["overall_priority"] >= 70 else "REVIEW" if merged["overall_priority"] >= 45 else "LOW"
    if verification_status != "VERIFIED":
        merged["reasons"] = list(dict.fromkeys(base.get("reasons", []) + ["Destination not independently verified"]))
    else:
        merged["reasons"] = list(dict.fromkeys(base.get("reasons", [])))
    return merged
