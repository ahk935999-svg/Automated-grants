from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlparse

@dataclass(frozen=True)
class VerificationResult:
    status: str
    hostname: str
    trust: str
    reason: str

def _matches(hostname, domain):
    hostname = hostname.lower().rstrip(".")
    domain = domain.lower().lstrip(".").rstrip(".")
    return hostname == domain or hostname.endswith("." + domain)

def verify_url(url, trusted_domains=None):
    trusted_domains = trusted_domains or {}
    try:
        parsed = urlparse(url)
    except ValueError:
        return VerificationResult("REJECTED", "", "unknown", "Malformed URL")

    if parsed.scheme != "https":
        return VerificationResult("REVIEW", parsed.hostname or "", "unknown", "HTTPS is required for trusted submission")

    if parsed.username or parsed.password:
        return VerificationResult("REVIEW", parsed.hostname or "", "unknown", "URL contains embedded credentials")

    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname:
        return VerificationResult("REJECTED", "", "unknown", "URL has no hostname")

    try:
        ip_address(hostname)
        return VerificationResult("REVIEW", hostname, "unknown", "IP-address destination requires human verification")
    except ValueError:
        pass

    for domain, trust in trusted_domains.items():
        if _matches(hostname, domain):
            return VerificationResult("VERIFIED", hostname, trust, f"Matches registered {trust} domain")

    return VerificationResult("REVIEW", hostname, "unknown", "Domain is not in the trusted-source registry")
