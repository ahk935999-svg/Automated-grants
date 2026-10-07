from typing import Any

HARD_HUMAN_GATES = {
    "legal_declaration",
    "captcha",
    "mfa",
    "signature",
    "payment",
    "unknown_fact",
    "eligibility_unknown",
    "missing_document",
    "untrusted_destination",
    "identity_sensitive_upload",
}

def can_auto_submit(policy: dict[str, Any], application_plan) -> tuple[bool, str]:
    if not policy.get("auto", {}).get("submit_application", False):
        return False, "Automatic submission is disabled by policy"
    if getattr(application_plan, "state", "") != "READY":
        return False, "Application is not in READY state"
    gates = set(getattr(application_plan, "gates", []) or [])
    hard = sorted(gates & HARD_HUMAN_GATES)
    if hard:
        return False, "Human gates remain: " + ", ".join(hard)
    return True, "Eligible for automatic submission by policy and gate state"
