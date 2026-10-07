from core.eligibility import assess
from core.models import Opportunity

def test_expired_deadline_is_ineligible():
    profile = {
        "identity": {"nationality": "Yemeni"},
        "education": {"degree_level": "Bachelor", "field": "Biomedical Engineering"},
    }
    opportunity = Opportunity(
        "Expired scholarship",
        "https://example.org/expired",
        "test",
        deadline="2026-10-01",
        raw={"eligibility": {"eligible_nationalities": ["*"]}},
    )
    result = assess(opportunity, profile)
    assert result.status == "INELIGIBLE"
    assert "Application deadline has passed" in result.blockers
