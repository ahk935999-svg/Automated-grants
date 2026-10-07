import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin,urlparse

import feedparser
import requests

from .models import Opportunity
from .scoring import infer_deadline,infer_funding

DISCOVERY_KEYWORDS=(
    "scholarship","funding","fellowship","grant","master","masters",
    "study","degree","research","internship","job","jobs","vacancy",
    "work","volunteer","exchange","mobility","programme","program",
    "opportunity","call for applications",
)

class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links=[]
        self._href=None
        self._text=[]

    def handle_starttag(self,tag,attrs):
        if tag.lower()!="a":
            return
        attributes=dict(attrs)
        self._href=attributes.get("href")
        self._text=[]

    def handle_data(self,data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self,tag):
        if tag.lower()!="a" or self._href is None:
            return
        text=" ".join(" ".join(self._text).split())
        self.links.append((self._href,text))
        self._href=None
        self._text=[]

def load_registry(path="config/source_registry.json"):
    return json.loads(Path(path).read_text(encoding="utf-8"))["sources"]

def _is_relevant_link(url,text):
    lowered=f"{text} {url}".lower()
    return any(keyword in lowered for keyword in DISCOVERY_KEYWORDS)

def extract_relevant_links(html,base_url,max_links=100):
    parser=_LinkParser()
    parser.feed(html)
    results=[]
    seen=set()
    for href,text in parser.links:
        if not href or not text:
            continue
        candidate=urljoin(base_url,href).strip()
        parsed=urlparse(candidate)
        if parsed.scheme!="https" or not parsed.netloc:
            continue
        if len(candidate)>500 or not _is_relevant_link(candidate,text):
            continue
        normalized=candidate.split("#",1)[0]
        if normalized==base_url.split("#",1)[0] or normalized in seen:
            continue
        seen.add(normalized)
        results.append((normalized,text))
        if len(results)>=max_links:
            break
    return results

def _discover_web_source(source,headers):
    response=requests.get(
        source["url"],headers=headers,timeout=20,allow_redirects=True
    )
    response.raise_for_status()
    content_type=response.headers.get("Content-Type","").lower()
    if "text/html" not in content_type:
        return [],{"source":source["name"],"error":"Source did not return HTML"}
    if len(response.content)>2_000_000:
        return [],{"source":source["name"],"error":"Source page exceeds 2 MB safety limit"}
    final_url=response.url
    links=extract_relevant_links(
        response.text,final_url,int(source.get("max_links",100))
    )
    opportunities=[]
    for url,title in links:
        summary=f"Discovered from official source: {source['name']}"
        combined=f"{title} {summary}"
        capabilities=source.get("capabilities",[])
        opportunity_type=capabilities[0] if capabilities else "opportunity"
        opportunities.append(Opportunity(
            title=title,url=url,source=source["name"],summary=summary,
            deadline=infer_deadline(combined),funding=infer_funding(combined),
            opportunity_type=opportunity_type,
            raw={
                "source_kind":source.get("kind"),
                "source_registry_id":source.get("id"),
                "discovered_from":final_url,
            },
        ))
    return opportunities,None

def discover_sources(sources):
    results,errors=[],[]
    headers={
        "User-Agent":(
            "Automated-Grants/production-v3 "
            "(+https://github.com/ahk935999-svg/Automated-grants)"
        ),
        "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    for source in sources:
        if not source.get("enabled"):
            continue
        try:
            if source.get("kind")=="rss":
                response=requests.get(
                    source["feed_url"],headers=headers,timeout=20
                )
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
                        raw={
                            "source_kind":source.get("kind"),
                            "source_registry_id":source.get("id"),
                            **dict(entry),
                        },
                    ))
            elif source.get("kind")=="official_web":
                found,error=_discover_web_source(source,headers)
                results.extend(found)
                if error:
                    errors.append(error)
        except (requests.RequestException,ValueError) as exc:
            errors.append({"source":source["name"],"error":str(exc)})
    deduped={}
    for item in results:
        if not item.url:
            continue
        deduped[item.url]=item
    return list(deduped.values()),errors

def discover_rss(sources):
    return discover_sources([source for source in sources if source.get("kind")=="rss"])
