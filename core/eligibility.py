from dataclasses import dataclass
from datetime import UTC, datetime
import re

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

def infer_published_eligibility(text, nationality=""):
    lowered = text.lower()
    meta = {}

    if nationality:
        pattern = (
            rf"(?:(?:not|cannot|can't)\s+(?:open|eligible)|except|excluding)"
            rf"[^.\n]{{0,100}}\b{re.escape(nationality.lower())}\b"
        )
        if re.search(pattern, lowered):
            meta["ineligible_nationalities"] = [nationality]

    if any(phrase in lowered for phrase in (
        "all nationalities", "all nationalities are eligible",
        "international students are eligible", "open to international students",
        "students from all countries",
    )):
        meta["eligible_nationalities"] = ["*"]
    elif nationality and nationality.lower() in lowered:
        marker_terms = (
            "eligible", "nationality", "nationalities", "citizens", "applicant"
        )
        if any(marker in lowered for marker in marker_terms):
            meta["eligible_nationalities"] = [nationality]

    if re.search(r"\b(ph\.?d\.?|doctoral|doctorate)\b", lowered):
        meta["required_degree_level"] = "phd"
    elif re.search(r"\b(master'?s?|master degree|msc|m\.sc\.)\b", lowered):
        meta["required_degree_level"] = "master"

    minimum = re.search(
        r"(?:minimum|at least|gpa of)\s*(?:a\s*)?(?:gpa\s*)?"
        r"(?:of\s*)?([0-4](?:\.\d+)?)",
        lowered,
    )
    if minimum:
        value = _number(minimum.group(1))
        if value is not None and value <= 4:
            meta["minimum_gpa"] = value
    return meta

def assess(opportunity, profile):
    reasons, blockers = [], []
    identity = profile.get("identity", {})
    education = profile.get("education", {})
    raw = opportunity.raw if isinstance(opportunity.raw, dict) else {}
    meta = dict(raw.get("eligibility", {}))
    if not meta:
        inferred = infer_published_eligibility(
            f"{opportunity.title} {opportunity.summary} {raw.get('detail_text', '')}",
            identity.get("nationality", ""),
        )
        meta.update(inferred)

    nationalities = [str(x).lower() for x in meta.get("eligible_nationalities", [])]
    excluded = [str(x).lower() for x in meta.get("ineligible_nationalities", [])]
    nationality = str(identity.get("nationality", "")).lower()

    if excluded and nationality in excluded:
        blockers.append("Nationality is explicitly excluded by published eligibility")
    elif nationalities:
        if "*" in nationalities or nationality in nationalities:
            reasons.append("Nationality appears compatible with published eligibility")
        else:
            blockers.append("Nationality not included in published eligibility")
    else:
        reasons.append("Nationality eligibility not explicitly available")

    required_degree = str(meta.get("required_degree_level", "")).lower()
    actual_degree = str(education.get("degree_level", "")).lower()
    progression = {
        ("bachelor", "master"), ("bsc", "master"),
        ("bachelor", "phd"), ("master", "phd"),
    }
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

    if opportunity.deadline:
        try:
            deadline = datetime.fromisoformat(opportunity.deadline).date()
            if deadline < datetime.now(UTC).date():
                blockers.append("Application deadline has passed")
        except ValueError:
            blockers.append("Published deadline could not be validated")

    if blockers:
        return EligibilityResult("INELIGIBLE", 0.0, reasons, blockers)
    if not nationalities and not excluded and not required_degree and minimum_gpa is None:
        return EligibilityResult("UNKNOWN", 55.0, reasons, blockers)
    return EligibilityResult("ELIGIBLE", 100.0, reasons, blockers)
