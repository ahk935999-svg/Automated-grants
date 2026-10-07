import re

GATE_PATTERNS = {
    "captcha": (
        r"\bcaptcha\b",
        r"re\s*captcha",
        r"hcaptcha",
        r"prove\s+you(?:'|’)re\s+human",
    ),
    "mfa": (
        r"multi[- ]factor authentication",
        r"two[- ]factor authentication",
        r"\b2fa\b",
        r"one[- ]time password",
        r"\botp\b",
    ),
    "signature": (
        r"electronic signature",
        r"signature required",
        r"sign(?:ature)?\s+(?:the|this)\s+(?:declaration|form|statement)",
    ),
    "payment": (
        r"application fee",
        r"application fees",
        r"non[- ]refundable fee",
        r"payment required",
        r"pay(?:ment)?\s+(?:the|an?)\s+(?:application )?fee",
    ),
    "legal_declaration": (
        r"\bi declare\b",
        r"legally binding",
        r"statement of truth",
        r"declaration that the information",
        r"false information.*(?:liable|penalt|disqualif)",
    ),
    "identity_sensitive_upload": (
        r"upload (?:a |your )?(?:passport|national id|identity document)",
        r"(?:passport|national id|identity document) (?:copy|scan|upload)",
        r"copy of (?:your )?(?:passport|national id|identity document)",
    ),
}

DOCUMENT_PATTERNS = {
    "recommendation": (
        r"recommendation letter",
        r"reference letter",
        r"letters? of recommendation",
    ),
    "research_proposal": (
        r"research proposal",
        r"study plan",
        r"research plan",
    ),
}

def _contains_any(text, patterns):
    return any(re.search(pattern, text, re.IGNORECASE | re.DOTALL) for pattern in patterns)

def detect_application_requirements(text: str) -> dict:
    normalized = " ".join((text or "").split())
    gates = sorted(
        gate for gate, patterns in GATE_PATTERNS.items()
        if _contains_any(normalized, patterns)
    )
    documents = sorted(
        document for document, patterns in DOCUMENT_PATTERNS.items()
        if _contains_any(normalized, patterns)
    )
    return {"gates": gates, "documents": documents}
