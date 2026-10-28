"""Bounded public search leads and CPU passage retrieval, never factual proof."""
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit, urlunsplit

from rank_bm25 import BM25Okapi
from tld import get_fld

from .core import Blocked, public_url


def tokens(text):
    normalized = "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))
    latin = re.findall(r"[a-z0-9]+", normalized)
    han = re.findall(r"[\u3400-\u9fff]+", text)
    return latin + [s[i:i+2] for s in han for i in range(max(1, len(s)-1))]


def topic_text(plan):
    return " ".join(str(plan.get(k, "")) for k in ("original_topic", "english_topic", "game")) + " " + " ".join(plan.get("queries_zh", []) + plan.get("queries_en", []))


def safe_lead(title, url, snippet="", **meta):
    if not isinstance(url, str) or not isinstance(title, str):
        return None
    try:
        p = urlsplit(url)
        if p.scheme == "http":
            url = urlunsplit(("https", p.netloc, p.path, p.query, ""))
        public_url(url)
    except (Blocked, ValueError):
        return None
    return {"title": title[:300], "url": url, "snippet": str(snippet)[:1000], **meta}


class Search:
    def __init__(self, web, ddgs_factory=None):
        self.web, self.errors = web, []
        if ddgs_factory is None:
            from ddgs import DDGS
            ddgs_factory = DDGS
        self.ddgs_factory = ddgs_factory

    def discover(self, query, language="en"):
        leads = []
        try:
            data, _ = self.web.get("https://www.bing.com/search", {"q": query, "format": "rss"})
            root = ET.fromstring(data)
            for item in root.findall(".//item")[:6]:
                lead = safe_lead(item.findtext("title", ""), item.findtext("link", ""), item.findtext("description", ""), engine="bing_rss", query=query, language=language)
                if lead:
                    leads.append(lead)
        except (Blocked, ET.ParseError) as exc:
            self.errors.append({"engine": "bing_rss", "error_type": type(exc).__name__})
        try:
            # Preserve the managed proxy and CA trust. No alternate route or
            # disabled certificate check is used when an engine is inaccessible.
            proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
            trust = os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("SSL_CERT_FILE") or True
            client = self.ddgs_factory(proxy=proxy, timeout=12, verify=trust)
            results = client.text(query, region="tw-zh" if language == "zh" else "us-en",
                                  max_results=6, backend="brave,duckduckgo,yahoo")
            for item in results:
                lead = safe_lead(item.get("title"), item.get("href"), item.get("body", ""), engine="ddgs", query=query, language=language)
                if lead:
                    leads.append(lead)
        except Exception as exc:
            self.errors.append({"engine": "ddgs", "error_type": type(exc).__name__})
        return leads


def rank_leads(leads, plan):
    unique = {}
    for lead in leads:
        unique.setdefault(lead["url"], lead)
    items = list(unique.values())
    if not items:
        return []
    corpus = [tokens(i.get("title", "") + " " + i.get("snippet", "")) or ["_"] for i in items]
    scores = BM25Okapi(corpus).get_scores(tokens(topic_text(plan)))
    ordered = sorted(range(len(items)), key=lambda i: float(scores[i]), reverse=True)
    groups = {}
    for i in ordered:
        domain = get_fld(items[i]["url"], fail_silently=True) or urlsplit(items[i]["url"]).hostname
        groups.setdefault(domain, []).append(items[i])
    # Read several publishers before a second article from the same publisher.
    ranked = []
    while any(groups.values()):
        for group in groups.values():
            if group:
                ranked.append(group.pop(0))
    return ranked


def passages(text, plan, budget=6000):
    """Return exact windows across the body, including evidence beyond its head."""
    if len(text) <= budget:
        return [{"start": 0, "end": len(text), "text": text}]
    spans = [(a, min(a+750, len(text))) for a in range(0, len(text), 650)]
    corpus = [tokens(text[a:b]) or ["_"] for a, b in spans]
    scores = BM25Okapi(corpus).get_scores(tokens(topic_text(plan)))
    order = sorted(range(len(spans)), key=lambda i: float(scores[i]), reverse=True)
    selected, size = [], 0
    for i in order:
        a, b = spans[i]
        if size + b-a > budget:
            continue
        selected.append((a, b))
        size += b-a
    merged = []
    for a, b in sorted(selected):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return [{"start": a, "end": b, "text": text[a:b]} for a, b in merged]
