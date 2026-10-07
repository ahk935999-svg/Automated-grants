import json
from pathlib import Path

def load_policy(path="config/policy.json"):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    data.setdefault("auto",{})
    data.setdefault("human_gates",[])
    data.setdefault("priority_threshold",70)
    data.setdefault("minimum_confidence_for_auto_draft",65)
    return data
