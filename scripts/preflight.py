import json
from pathlib import Path

from core.policy import load_policy
from core.profile import load_profile, sensitive_fields_present, validate_profile
from core.sources import load_registry

def main():
    profile_path = Path("profile/profile.json")
    registry_path = Path("config/source_registry.json")
    policy_path = Path("config/policy.json")

    for path in (profile_path, registry_path, policy_path):
        if not path.exists():
            raise SystemExit(f"MISSING: {path}")

    profile = load_profile()
    errors = validate_profile(profile)
    if errors:
        raise SystemExit("PROFILE ERROR: " + "; ".join(errors))

    sensitive = sensitive_fields_present(profile)
    if sensitive:
        raise SystemExit("PUBLIC PROFILE CONTAINS SENSITIVE FIELDS: " + ", ".join(sensitive))

    registry = load_registry()
    for source in registry:
        if source.get("enabled") and not source.get("domain"):
            raise SystemExit(f"SOURCE ERROR: missing domain for {source.get('id')}")

    policy = load_policy()
    required_gates = {"captcha", "mfa", "signature", "payment", "unknown_fact", "untrusted_destination"}
    missing = required_gates - set(policy.get("human_gates", []))
    if missing:
        raise SystemExit("POLICY ERROR: missing human gates: " + ", ".join(sorted(missing)))

    print(json.dumps({
        "status": "OK",
        "profile": str(profile_path),
        "sources": len(registry),
        "priority_threshold": policy["priority_threshold"],
        "sensitive_public_fields": 0
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
