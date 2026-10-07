import json
from pathlib import Path

import feedparser
import requests

from .models import Opportunity
from .scoring import infer_deadline, infer_funding

def load_registry(path="config/source_registry.json"):
    return json.loads(Path(path).read_text(encoding="utf-8"))["sources"]

def discover_rss(sources):
    results,errors=[],[]
    headers={"User-Agent":"Automated-Grants/production-v3 (+https://github.com/ahk935999-svg/Automated-grants)"}
    for source in sources:
        if not source.get("enabled") or source.get("kind")!="rss":
            continue
        try:
            response=requests.get(source["feed_url"],headers=headers,timeout=20)
            response.raise_for_status()
            parsed=feedparser.parse(response.content[:2_000_000])
            for entry in parsed.entries:
                title=entry.get("title","Untitled").strip()
                summary=entry.get("summary","").strip()
                combined=f"{title} {summary}"
                results.append(Opportunity(
                    title=title,url=entry.get("link","").strip(),
                    source=source["name"],summary=summary,
                    deadline=infer_deadline(combined),funding=infer_funding(combined),
                    raw=dict(entry)
                ))
        except (requests.RequestException,ValueError) as exc:
            errors.append({"source":source["name"],"error":str(exc)})
    deduped={item.url:item for item in results if item.url}
    return list(deduped.values()),errors
