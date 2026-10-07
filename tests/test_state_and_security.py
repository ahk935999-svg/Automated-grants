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
        conn.execute(
            "INSERT INTO opportunities(title,url,source) VALUES(?,?,?)",
            ("Test","https://example.org/opportunity","test")
        )
        opportunity_id=conn.execute(
            "SELECT id FROM opportunities WHERE url=?",
            ("https://example.org/opportunity",)
        ).fetchone()["id"]
        first=upsert_application(conn,opportunity_id,"SUBMITTED")
        second=upsert_application(conn,opportunity_id,"INTERVENTION")
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

def test_legacy_schema_migrates(tmp_path):
    db=str(tmp_path/"legacy.db")
    with connect(db) as conn:
        conn.execute("CREATE TABLE opportunities (id INTEGER PRIMARY KEY, title TEXT)")
    init_db(db)
    with connect(db) as conn:
        cols={row["name"] for row in conn.execute("PRAGMA table_info(opportunities)")}
    assert {"verification_status","eligibility_status","first_seen_at","last_seen_at"}<=cols
