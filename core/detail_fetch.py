from html.parser import HTMLParser
from urllib.parse import urlparse

import requests

from .network import is_public_host
from .verification import verify_url

MAX_BYTES = 1_500_000
MAX_TEXT = 30_000

class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data.strip())

def fetch_public_page(url, timeout=15, allowed_domains=None):
    allowed_domains = allowed_domains or {}
    initial = verify_url(url, allowed_domains)
    if allowed_domains and initial.status != "VERIFIED":
        return None
    if not is_public_host(initial.hostname):
        return None

    response = requests.get(
        url,
        headers={"User-Agent": "Automated-Grants/production-v3"},
        timeout=timeout,
        allow_redirects=True,
        stream=True,
    )
    try:
        response.raise_for_status()
        final_url = response.url
        final = verify_url(final_url, allowed_domains)
        if allowed_domains and final.status != "VERIFIED":
            return None
        if not is_public_host(final.hostname):
            return None
        if "text/html" not in response.headers.get("Content-Type", "").lower():
            return None

        chunks = []
        total = 0
        for chunk in response.iter_content(chunk_size=64_000):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_BYTES:
                return None
            chunks.append(chunk)
        html = b"".join(chunks).decode(
            response.encoding or "utf-8", errors="replace"
        )
    finally:
        response.close()

    parser = _TextParser()
    parser.feed(html)
    text = " ".join(" ".join(parser.parts).split())
    return text[:MAX_TEXT] or None
