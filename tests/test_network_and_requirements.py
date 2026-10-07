from core.application_ops import build_plan
from core.eligibility import assess
from core.models import Opportunity
from core.network import canonicalize_url, is_public_host
from core.requirements import detect_application_requirements
from core.submission_guard import can_auto_submit
from core.verification import verify_url

def profile():
    return {
        "identity": {"nationality": "Yemeni", "email": "test@example.org"},
        "education": {"degree_level": "Bachelor", "field": "Biomedical Engineering"},
        "preferences": {"opportunity_types": ["scholarship"]},
        "documents": {
            "cv": "cv.pdf", "transcript": "transcript.pdf",
            "degree": "degree.pdf", "recommendations": [],
        },
    }

def test_canonicalize_url_removes_tracking_and_fragment():
    value = canonicalize_url(
        "https://Example.org/path/?utm_source=x&keep=1#details"
    )
    assert value == "https://example.org/path?keep=1"

def test_private_ip_is_not_public():
    assert is_public_host("127.0.0.1") is False

def test_requirements_detect_high_risk_gates():
    result = detect_application_requirements(
        "Upload your passport. An application fee is required. "
        "I declare that the information is correct. Complete the reCAPTCHA."
    )
    assert {
        "identity_sensitive_upload", "payment",
        "legal_declaration", "captcha",
    } <= set(result["gates"])

def test_build_plan_inherits_detected_human_gates():
    opportunity = Opportunity(
        "Test",
        "https://eures.europa.eu/jobs",
        "EURES",
        raw={
            "eligibility": {
                "eligible_nationalities": ["*"],
                "required_degree_level": "master",
            },
            "detail_text": "Upload your passport and complete two-factor authentication.",
        },
    )
    eligibility = assess(opportunity, profile())
    verification = verify_url(
        opportunity.url, {"eures.europa.eu": "official"}
    )
    plan = build_plan(opportunity, profile(), verification, eligibility)
    assert plan.state == "INTERVENTION"
    assert {"identity_sensitive_upload", "mfa"} <= set(plan.gates)

def test_auto_submit_requires_policy_and_gate_clearance():
    class Ready:
        state = "READY"
        gates = []

    class Gated:
        state = "READY"
        gates = ["captcha"]

    policy = {"auto": {"submit_application": True}}
    assert can_auto_submit(policy, Ready())[0] is True
    assert can_auto_submit(policy, Gated())[0] is False
    assert can_auto_submit(
        {"auto": {"submit_application": False}}, Ready()
    )[0] is False
