from dataclasses import dataclass

HUMAN_GATES = {
    "legal_declaration",
    "captcha",
    "mfa",
    "signature",
    "payment",
    "unknown_fact",
    "untrusted_destination",
    "identity_sensitive_upload",
}

@dataclass(frozen=True)
class ApplicationPlan:
    state: str
    missing_documents: list[str]
    gates: list[str]
    next_action: str

def build_plan(opportunity, profile, verification):
    documents = profile.get("documents", {})
    missing = [key for key in ("cv", "transcript", "degree") if not documents.get(key)]

    gates = []
    if verification.status != "VERIFIED":
        gates.append("untrusted_destination")

    if not profile.get("identity", {}).get("email"):
        gates.append("unknown_fact")

    if missing:
        gates.append("unknown_fact")

    if gates:
        return ApplicationPlan(
            state="INTERVENTION",
            missing_documents=missing,
            gates=sorted(set(gates)),
            next_action="Complete missing profile/documents and verify destination before submission"
        )

    return ApplicationPlan(
        state="READY",
        missing_documents=[],
        gates=[],
        next_action="Application may enter the submission adapter after final human gates"
    )
