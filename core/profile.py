import json
from pathlib import Path
from typing import Any

def load_profile(path="profile/profile.json", raw_json=None) -> dict[str, Any]:
    if raw_json:
        return json.loads(raw_json)
    return json.loads(Path(path).read_text(encoding="utf-8"))

def validate_profile(profile: dict[str, Any]) -> list[str]:
    errors = []
    if not profile.get("identity", {}).get("nationality"):
        errors.append("identity.nationality is missing")
    if not profile.get("education", {}).get("field"):
        errors.append("education.field is missing")
    if not profile.get("preferences", {}).get("opportunity_types"):
        errors.append("preferences.opportunity_types is missing")
    return errors

def sensitive_fields_present(profile: dict[str, Any]) -> list[str]:
    identity = profile.get("identity", {})
    documents = profile.get("documents", {})
    found = []
    if identity.get("passport_number"):
        found.append("identity.passport_number")
    if documents.get("passport"):
        found.append("documents.passport")
    return found
