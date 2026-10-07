import json
from pathlib import Path

from core.config import Settings
from core.policy import load_policy
from core.profile import load_profile,sensitive_fields_present,validate_profile
from core.sources import load_registry

def main():
    settings=Settings()
    for path in (
        Path(settings.profile_path),
        Path("config/source_registry.json"),
        Path("config/policy.json"),
    ):
        if not path.exists():
            raise SystemExit(f"MISSING: {path}")

    public_profile=load_profile(settings.profile_path)
    public_sensitive=sensitive_fields_present(public_profile)
    if public_sensitive:
        raise SystemExit(
            "PUBLIC PROFILE CONTAINS SENSITIVE VALUES: "
            + ", ".join(public_sensitive)
        )

    profile=load_profile(settings.profile_path,settings.applicant_profile_json)
    errors=validate_profile(profile)
    if errors:
        raise SystemExit("PROFILE ERROR: "+"; ".join(errors))

    registry=load_registry()
    for source in registry:
        source_id=source.get("id","unknown")
        if source.get("enabled") and not source.get("domain"):
            raise SystemExit(f"SOURCE ERROR: missing domain for {source_id}")

    policy=load_policy()
    required={"captcha","mfa","signature","payment","unknown_fact","untrusted_destination"}
    missing=required-set(policy.get("human_gates",[]))
    if missing:
        raise SystemExit(
            "POLICY ERROR: missing human gates: "+", ".join(sorted(missing))
        )

    print(json.dumps({
        "status":"OK",
        "profile_source":"CI_SECRET" if settings.applicant_profile_json else settings.profile_path,
        "sources":len(registry),
        "priority_threshold":policy["priority_threshold"],
        "sensitive_public_fields":0,
    },ensure_ascii=False))

if __name__=="__main__":
    main()
