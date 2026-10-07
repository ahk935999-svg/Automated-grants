from dataclasses import dataclass

@dataclass(frozen=True)
class EligibilityResult:
    status: str
    score: float
    reasons: list[str]
    blockers: list[str]

def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def assess(opportunity, profile):
    reasons, blockers = [], []
    identity = profile.get("identity", {})
    education = profile.get("education", {})
    meta = opportunity.raw.get("eligibility", {}) if isinstance(opportunity.raw, dict) else {}

    nationalities = [str(x).lower() for x in meta.get("eligible_nationalities", [])]
    nationality = str(identity.get("nationality", "")).lower()
    if nationalities:
        if nationality in nationalities:
            reasons.append("Nationality explicitly included")
        else:
            blockers.append("Nationality not included in published eligibility")
    else:
        reasons.append("Nationality eligibility not explicitly available")

    required_degree = str(meta.get("required_degree_level", "")).lower()
    actual_degree = str(education.get("degree_level", "")).lower()
    progression = {("bachelor", "master"), ("bsc", "master"), ("bachelor", "phd"), ("master", "phd")}
    if required_degree and actual_degree:
        if actual_degree == required_degree or (actual_degree, required_degree) in progression:
            reasons.append("Degree level appears compatible")
        else:
            blockers.append(f"Degree requirement mismatch: {required_degree}")
    elif required_degree:
        blockers.append("Applicant degree level missing")

    minimum_gpa = _number(meta.get("minimum_gpa"))
    applicant_gpa = _number(education.get("gpa"))
    if minimum_gpa is not None:
        if applicant_gpa is None:
            blockers.append("Applicant GPA missing")
        elif applicant_gpa >= minimum_gpa:
            reasons.append("GPA meets published minimum")
        else:
            blockers.append("GPA below published minimum")

    if blockers:
        return EligibilityResult("INELIGIBLE", 0.0, reasons, blockers)
    if not nationalities and not required_degree and minimum_gpa is None:
        return EligibilityResult("UNKNOWN", 55.0, reasons, blockers)
    return EligibilityResult("ELIGIBLE", 100.0, reasons, blockers)
