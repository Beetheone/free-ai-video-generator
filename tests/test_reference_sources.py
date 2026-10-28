"""Synthetic bibliographies must be fetched and never create factual evidence."""
from documentary.references import reference_leads
from documentary.research import publisher


def test_bibliography_uses_actual_page_links_and_keeps_downloaded_bytes():
    raw = b'''<html><body><ol class="references"><li id="cite_note-1"><span class="reference-text">
    Fictional hidden bridge archive. <a class="external text" href="https://news.fixture.org/bridge">Original</a>
    <a class="external" href="https://127.0.0.1/private">unsafe</a>
    </span></li></ol></body></html>'''
    class Page:
        title = "Fictional bridge"
        fullurl = "https://en.wikipedia.org/wiki/Fictional_bridge"
        def exists(self): return True
    class Wiki:
        def __init__(self, **kwargs):
            assert kwargs['allow_redirects'] is False
            assert kwargs['language'] == 'en'
        def page(self, title): return Page()
    class Web:
        def get(self, url):
            assert url == Page.fullurl
            return raw, url
    leads, cache, errors = reference_leads(Web(), {'reference_titles_en': ['Fictional bridge']}, Wiki)
    assert not errors
    assert cache[Page.fullurl][0] == raw
    assert {l['engine'] for l in leads} == {'wikipedia_seed', 'wikipedia_references'}
    assert 'https://news.fixture.org/bridge' in {l['url'] for l in leads}
    assert all('127.0.0.1' not in l['url'] for l in leads)
    assert next(l for l in leads if l['engine'] == 'wikipedia_references')['referrer'] == Page.fullurl


def test_missing_suggested_page_does_not_become_a_source():
    class Page:
        def exists(self): return False
    class Wiki:
        def __init__(self, **kwargs): pass
        def page(self, title): return Page()
    class Web:
        def get(self, *a): raise AssertionError('Missing page must not be downloaded')
    leads, cache, errors = reference_leads(Web(), {'reference_titles_en': ['Missing fixture']}, Wiki)
    assert not leads and not cache
    assert errors[0]['error_type'] == 'PageNotFound'


def test_archive_is_not_an_independent_publisher_of_same_original():
    assert publisher('https://web.archive.org/web/20030101000000/https://news.example.org/story') == publisher('https://news.example.org/story')
