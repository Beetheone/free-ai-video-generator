"""Canonical encyclopedia leads and their real external bibliographies."""
from urllib.parse import urljoin, urlsplit

from lxml import html

from .search import safe_lead


def reference_leads(web, plan, wiki_factory=None):
    titles = plan.get("reference_titles_en", [])[:2]
    leads, pages, errors = [], {}, []
    for url in plan.get("candidate_urls", [])[:3]:
        lead = safe_lead(url, url, engine="model_suggested_url")
        if lead:
            leads.append(lead)
    if not titles:
        return leads, pages, errors
    if wiki_factory is None:
        from wikipediaapi import Wikipedia
        wiki_factory = Wikipedia
    wiki = wiki_factory(language="en", user_agent="GameDocumentary/1.0 (https://github.com/Beetheone/free-ai-video-generator)",
                        timeout=(10, 20), allow_redirects=False)
    for title in titles:
        try:
            page = wiki.page(title)
            if not page.exists():
                errors.append({"engine": "wikipedia_references", "error_type": "PageNotFound"})
                continue
            url = page.fullurl
            # Requests still go through the normal bounded, redirect-validating
            # downloader. Model-suggested titles/URLs are never source evidence.
            raw, final_url = web.get(url)
            pages[url] = (raw, final_url)
            lead = safe_lead(page.title, url, engine="wikipedia_seed")
            if lead:
                leads.append(lead)
            tree = html.fromstring(raw)
            seen = set()
            for item in tree.xpath('//li[starts-with(@id, "cite_note") or contains(concat(" ",normalize-space(@class)," ")," citation ")]')[:250]:
                context = " ".join(item.text_content().split())[:1000]
                for anchor in item.xpath('.//a[contains(concat(" ",normalize-space(@class)," ")," external ")]'):
                    target = urljoin(final_url, anchor.get("href", ""))
                    if target in seen or urlsplit(target).hostname == urlsplit(final_url).hostname:
                        continue
                    seen.add(target)
                    lead = safe_lead(context[:300], target, context, engine="wikipedia_references", referrer=final_url)
                    if lead:
                        leads.append(lead)
        except Exception as exc:
            errors.append({"engine": "wikipedia_references", "error_type": type(exc).__name__})
    return leads, pages, errors
