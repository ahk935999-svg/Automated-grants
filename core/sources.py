import feedparser
from .models import Opportunity

DEFAULT_FEEDS = {
    "OpportunityDesk": "https://opportunitydesk.org/feed/",
    "ScholarshipsAds": "https://www.scholarshipsads.com/feed/",
}

def discover_rss(feeds=None):
    results = []
    for source, url in (feeds or DEFAULT_FEEDS).items():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            results.append(Opportunity(
                title=entry.get("title", "Untitled").strip(),
                url=entry.get("link", "").strip(),
                source=source,
                summary=entry.get("summary", "").strip(),
                raw=dict(entry),
            ))
    return [x for x in results if x.url]
