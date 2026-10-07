from core.models import Opportunity
from core.profile import validate_profile
from core.scoring import funding_score, urgency_score, deterministic_evaluation

def test_funding_score():
    assert funding_score("Fully funded tuition and stipend") == 100.0
    assert funding_score(None) == 20.0

def test_urgency_invalid_is_safe():
    assert urgency_score("not-a-date") == 10.0

def test_profile_validation():
    profile = {
        "identity": {"nationality": "Yemeni"},
        "education": {"field": "Biomedical Engineering"},
        "preferences": {"opportunity_types": ["scholarship"]}
    }
    assert validate_profile(profile) == []

def test_deterministic_evaluation():
    profile = {
        "identity": {"nationality": "Yemeni"},
        "education": {"field": "Biomedical Engineering"},
        "preferences": {"keywords": ["medical devices"]}
    }
    opportunity = Opportunity(
        "Biomedical Engineering Scholarship",
        "https://example.org/x",
        "test",
        "medical devices",
        funding="Fully funded"
    )
    result = deterministic_evaluation(opportunity, profile)
    assert result["overall_priority"] >= 70
