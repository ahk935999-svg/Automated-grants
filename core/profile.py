import json
from pathlib import Path
from typing import Any

def load_profile(path: str = "profile/profile.json") -> dict[str, Any]:
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
