from dataclasses import dataclass

HUMAN_GATES={
    "legal_declaration","captcha","mfa","signature","payment",
    "unknown_fact","eligibility_unknown","missing_document",
    "untrusted_destination","identity_sensitive_upload",
}

REQUIRED_DOCUMENTS=("cv","transcript","degree")

@dataclass(frozen=True)
class ApplicationPlan:
    state:str
    missing_documents:list[str]
    gates:list[str]
    next_action:str

def build_plan(opportunity,profile,verification,eligibility):
    if eligibility.status=="INELIGIBLE":
        return ApplicationPlan(
            "REJECTED",[],[],"Do not apply: deterministic eligibility blocker"
        )

    if eligibility.status=="UNKNOWN":
        return ApplicationPlan(
            "INTERVENTION",[],["eligibility_unknown"],
            "Confirm unresolved eligibility facts from the official opportunity page"
        )

    documents=profile.get("documents",{})
    missing=[key for key in REQUIRED_DOCUMENTS if not documents.get(key)]
    gates=[]

    if verification.status!="VERIFIED":
        gates.append("untrusted_destination")
    if not profile.get("identity",{}).get("email"):
        gates.append("unknown_fact")
    if missing:
        gates.append("missing_document")

    if gates:
        return ApplicationPlan(
            "INTERVENTION",missing,sorted(set(gates)),"Resolve gates before submission"
        )

    return ApplicationPlan(
        "READY",[],[],
        "Ready for a supported submission adapter, subject to final human gates"
    )
