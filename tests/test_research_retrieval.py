"""Synthetic article/search fixtures verify mechanics, not real game history."""
from urllib.parse import urlsplit

import pytest

from documentary import pipeline
from documentary.core import Blocked, save
from documentary.research import fact_check, plan_repair
from documentary.search import Search, passages, rank_leads, tokens


def test_exact_late_passage_is_retrieved_without_fabricating_or_exceeding_context():
    context = "Unrelated fictional horticulture and weather observations. " * 330
    relevant = "The fictional Runestone game's hidden bridge was documented in the imaginary test archive. " * 5
    text = context + "\n" + relevant + "\n" + context
    plan = {"english_topic": "Runestone hidden bridge archive", "game": "虛構遊戲"}
    selected = passages(text, plan)
    assert len(context) > 12000
    assert any("Runestone" in p["text"] and p["start"] > 6000 for p in selected)
    assert sum(len(p["text"]) for p in selected) <= 6000
    assert all(text[p["start"]:p["end"]] == p["text"] for p in selected)


def test_rank_leads_prefers_topic_and_multiple_publishers():
    leads = [
        {"url": "https://unrelated.example.net/sports", "title": "Local sports results"},
        {"url": "https://one.example.org/a", "title": "Runestone hidden bridge archive"},
        {"url": "https://one.example.org/b", "title": "Runestone hidden bridge details"},
        {"url": "https://two.example.com/c", "title": "Runestone hidden bridge history"},
    ]
    ranked = rank_leads(leads, {"english_topic": "Runestone hidden bridge", "game": "Runestone"})
    assert "sports" not in ranked[0]["url"]
    assert len({urlsplit(x["url"]).hostname for x in ranked[:3]}) == 3
    assert "pokemon" in tokens("Pokémon")


def test_search_keeps_proxy_and_tls_and_rejects_private_leads(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.fixture:8080")
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", "/fixture-ca.pem")
    class Web:
        def get(self, *a):
            return b"<rss><channel/></rss>", a[0]
    class SDK:
        def __init__(self, **kw):
            assert kw == {"proxy": "http://proxy.fixture:8080", "timeout": 12, "verify": "/fixture-ca.pem"}
        def text(self, query, **kw):
            assert kw["backend"] == "brave,duckduckgo,yahoo"
            return [{"title": "Fixture", "href": "http://fixture.example.org/article", "body": "Not evidence"},
                    {"title": "Private", "href": "https://127.0.0.1/private"}]
    search = Search(Web(), ddgs_factory=SDK)
    results = search.discover("虛構遊戲", "zh")
    assert len(results) == 1 and results[0]["url"] == "https://fixture.example.org/article"


def test_prefetched_reference_body_is_used_before_keyword_heavy_summaries(tmp_path, monkeypatch):
    import importlib
    module = importlib.import_module('documentary.research')
    wiki_url = 'https://en.wikipedia.org/wiki/Synthetic_fixture'
    body = ('<html><body><article><h1>Explicit fixture</h1>' + '<p>Fictional source body for a retrieval test. ' + 'This is synthetic evidence only. ' * 30 + '</p></article></body></html>').encode()
    monkeypatch.setattr(module, 'reference_leads', lambda *a: ([{'url': wiki_url, 'title': 'Fixture', 'engine': 'wikipedia_seed'}], {wiki_url: (body, wiki_url)}, []))
    class Web:
        def get(self, url):
            assert url != wiki_url, 'Already downloaded canonical body must be reused'
            return body, url
    class SearchFixture:
        def discover(self, *a):
            return [{'url': f'https://publisher{i}.example.org/article', 'title': 'Synthetic bridge synthetic bridge'} for i in range(20)]
    sources = module.research(Web(), {'english_topic': 'synthetic bridge', 'queries_zh': ['虛構橋樑'], 'queries_en': ['synthetic bridge']}, tmp_path, searcher=SearchFixture())
    assert sources[0]['url'] == wiki_url
    assert len(sources) == 12


def test_empty_excerpt_cache_does_not_repeat_inference_or_pass_claim_gate(tmp_path):
    class Model:
        selections = 0
        def json(self, instruction, payload):
            if "quote_candidates" in payload:
                self.selections += 1
                return {"quote_ids": []}
            return {"claims": []}
    model, cache = Model(), {}
    sources = [{"id": f"S{i}", "text": f"Fictional unrelated body {i}. " * 8,
                "url": f"https://fixture{i}.example.org/article"} for i in range(3)]
    for _ in range(2):
        with pytest.raises(Blocked) as exc:
            fact_check(model, {"english_topic": "fictional bridge"}, sources, tmp_path, quote_cache=cache)
        assert exc.value.code == "EVIDENCE_INSUFFICIENT"
    assert model.selections == 3


def test_gap_plan_uses_actual_missing_claims_and_does_not_repeat_seed_pages(tmp_path):
    save(tmp_path / 'evidence_draft.json', {'claims': [{'statement': 'Explicit synthetic candidate'}], 'uncertainties': ['Missing fictional chronology']})
    save(tmp_path / 'research_excerpts.json', [{'id': 'S1'}])
    plan = {'english_topic': 'Synthetic topic', 'queries_zh': ['舊查詢'], 'queries_en': ['old query'],
            'reference_titles_en': ['Old page'], 'candidate_urls': ['https://fixture.example.org/old']}
    class Model:
        def json(self, instruction, payload):
            assert payload['candidate_claims'][0]['statement'] == 'Explicit synthetic candidate'
            assert payload['uncertainties'] == ['Missing fictional chronology']
            return {'queries_zh': ['新查詢'], 'queries_en': ['new query'], 'reference_titles_en': ['Old_page', 'New page'],
                    'candidate_urls': ['https://fixture.example.org/old', 'https://fixture.example.org/new']}
    repaired = plan_repair(Model(), plan, [{'id': 'S1', 'url': 'https://fixture.example.org/old'}], tmp_path)
    assert repaired['reference_titles_en'] == ['New page']
    assert repaired['candidate_urls'] == ['https://fixture.example.org/new']
    assert plan['queries_en'] == ['old query']


@pytest.mark.parametrize("code,repairs,status", [("EVIDENCE_INSUFFICIENT", 1, "RESEARCH_READY"),
                                               ("MODEL_UNAVAILABLE", 0, "BLOCKED")])
def test_repair_is_bounded_and_never_retries_auth_or_quota(tmp_path, monkeypatch, code, repairs, status):
    sources = [{"id": f"S{i}", "title": "Fixture", "text": "Synthetic source only", "url": f"https://fixture{i}.example.org/article"} for i in range(3)]
    monkeypatch.setattr(pipeline, "plan_topic", lambda *a: {"english_topic": "synthetic"})
    calls = {"facts": 0, "repairs": 0}
    def research(*a, **k):
        return sources
    def check(*a, **k):
        calls["facts"] += 1
        if calls["facts"] == 1:
            raise Blocked(code, "Explicit fixture only")
        return {"claims": []}
    def repair(*a):
        calls["repairs"] += 1
        return {}
    monkeypatch.setattr(pipeline, "research", research)
    monkeypatch.setattr(pipeline, "fact_check", check)
    monkeypatch.setattr(pipeline, "plan_repair", repair)
    report = pipeline.run_pipeline("合成測試", 12, tmp_path / "out", model=object(), web=object(), stop_after="research")
    assert report["status"] == status
    assert calls["repairs"] == repairs
    assert calls["facts"] == 1 + repairs
    assert report["status"] != "COMPLETE_AUTOMATED_CHECKS"
