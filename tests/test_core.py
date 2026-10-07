from core.application_ops import build_plan
from core.eligibility import assess
from core.models import Opportunity
from core.profile import validate_profile
from core.scoring import deterministic_evaluation,funding_score,urgency_score
from core.verification import verify_url

def base_profile():
    return {
        "identity":{"nationality":"Yemeni","email":"test@example.org"},
        "education":{"degree_level":"Bachelor","field":"Biomedical Engineering"},
        "preferences":{"opportunity_types":["scholarship"],"keywords":["medical devices"]},
        "documents":{"cv":"cv.pdf","transcript":"transcript.pdf","degree":"degree.pdf"},
    }

def eligible_opportunity(title,url="https://example.org/x"):
    return Opportunity(
        title,url,"test","Biomedical Engineering medical devices",
        funding="Fully funded",
        raw={"eligibility":{
            "eligible_nationalities":["Yemeni"],
            "required_degree_level":"master"
        }},
    )

def test_funding_score():
    assert funding_score("Fully funded tuition and stipend")==100.0
    assert funding_score(None)==20.0

def test_urgency_invalid_is_safe():
    assert urgency_score("not-a-date")==10.0

def test_profile_validation():
    assert validate_profile(base_profile())==[]

def test_deterministic_evaluation():
    profile=base_profile()
    opportunity=eligible_opportunity("Biomedical Engineering Scholarship")
    eligibility=assess(opportunity,profile)
    result=deterministic_evaluation(opportunity,profile,eligibility)
    assert result["overall_priority"]>=70

def test_ineligible_gpa_is_hard_blocker():
    profile=base_profile()
    profile["education"]["gpa"]="2.0"
    opportunity=eligible_opportunity("Master scholarship")
    opportunity.raw["eligibility"]["minimum_gpa"]=3.0
    eligibility=assess(opportunity,profile)
    assert eligibility.status=="INELIGIBLE"
    assert deterministic_evaluation(opportunity,profile,eligibility)["decision"]=="LOW"

def test_untrusted_destination_requires_gate():
    profile=base_profile()
    opportunity=eligible_opportunity("Test","https://example.com/apply")
    eligibility=assess(opportunity,profile)
    verification=verify_url(opportunity.url,{"eures.europa.eu":"official"})
    plan=build_plan(opportunity,profile,verification,eligibility)
    assert "untrusted_destination" in plan.gates
    assert plan.state=="INTERVENTION"

def test_official_destination_can_be_ready():
    profile=base_profile()
    opportunity=eligible_opportunity("Test","https://eures.europa.eu/jobs")
    eligibility=assess(opportunity,profile)
    verification=verify_url(opportunity.url,{"eures.europa.eu":"official"})
    plan=build_plan(opportunity,profile,verification,eligibility)
    assert plan.state=="READY"
