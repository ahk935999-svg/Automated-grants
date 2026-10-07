from core.application_ops import build_plan
from core.db import connect,init_db,upsert_application
from core.eligibility import assess
from core.models import Opportunity
from core.verification import verify_url

def profile_ready():
    return {
        "identity":{"nationality":"Yemeni","email":"test@example.org"},
        "education":{"degree_level":"Bachelor","field":"Biomedical Engineering"},
        "preferences":{"opportunity_types":["scholarship"]},
        "documents":{"cv":"cv.pdf","transcript":"transcript.pdf","degree":"degree.pdf"},
    }

def test_application_state_never_regresses(tmp_path):
    db=str(tmp_path/"test.db")
    init_db(db)
    with connect(db) as conn:
        first=upsert_application(conn,1,"SUBMITTED")
        second=upsert_application(conn,1,"INTERVENTION")
    assert first[1]=="SUBMITTED"
    assert second[1]=="SUBMITTED"
    assert second[2] is False

def test_unknown_eligibility_blocks_ready():
    profile=profile_ready()
    opportunity=Opportunity("Test","https://eures.europa.eu/jobs","test")
    eligibility=assess(opportunity,profile)
    verification=verify_url(opportunity.url,{"eures.europa.eu":"official"})
    plan=build_plan(opportunity,profile,verification,eligibility)
    assert plan.state=="INTERVENTION"
    assert "unknown_fact" in plan.gates
