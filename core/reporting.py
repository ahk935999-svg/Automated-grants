import json
from datetime import UTC,datetime
from pathlib import Path

def write_run_report(path,payload):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    report={"generated_at":datetime.now(UTC).isoformat(),**payload}
    Path(path).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report
