from dataclasses import dataclass, field
from typing import Any

@dataclass
class Opportunity:
    title: str
    url: str
    source: str
    summary: str = ""
    country: str | None = None
    deadline: str | None = None
    funding: str | None = None
    opportunity_type: str = "scholarship"
    raw: dict[str, Any] = field(default_factory=dict)

@dataclass
class Evaluation:
    eligibility_score: float
    profile_match_score: float
    funding_score: float
    urgency_score: float
    competitiveness_score: float
    confidence_score: float
    overall_priority: float
    decision: str
    reasons: list[str] = field(default_factory=list)
