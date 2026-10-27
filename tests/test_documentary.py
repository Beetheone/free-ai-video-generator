"""Synthetic fixtures test mechanics only; they are NEVER real research/gameplay results."""
import copy
import json
from pathlib import Path

import pytest

from documentary.core import Blocked, Model, Web, command, duration, public_url
from documentary.footage import Library, detect_shots, licensed_record
from documentary.pipeline import main, run_pipeline
from documentary.production import ass_file, inspect_media, render, thumbnail, validate_cues
from documentary.research import fact_check, plan_topic, research, validate_claims, validate_script


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://example.com", "https://127.0.0.1/a", "https://10.0.0.1", "https://localhost", "https://foo.local", "https://user:secret@example.com", "https://example.com:8080"])
def test_private_urls_rejected(url):
    with pytest.raises(Blocked, match="permitted"):
        public_url(url)


def test_redirect_rechecked(monkeypatch):
    class Response:
        is_redirect = True
        url = "https://example.org/"
        headers = {"Location": "https://127.0.0.1/private"}
        def __enter__(self): return self
        def __exit__(self, *args): pass
    web = Web()
    monkeypatch.setattr(web.session, "get", lambda *args, **kw: Response())
    with pytest.raises(Blocked) as exc:
        web.get("https://example.org/")
    assert exc.value.code == "UNSAFE_URL"


def test_model_missing_credential(monkeypatch):
    for key in ("LLM_API_KEY", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(Blocked) as exc:
        Model().json("test", {})
    assert exc.value.code == "MODEL_CREDENTIAL_REQUIRED"


def test_model_error_does_not_log_secret(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fixture-secret-do-not-log")
    class Response:
        status_code = 429
        text = "fixture-secret-do-not-log"
    monkeypatch.setattr("documentary.core.requests.post", lambda *a, **k: Response())
    with pytest.raises(Blocked) as exc:
        Model().json("test", {})
    assert "429" in str(exc.value) and "fixture-secret" not in str(exc.value)


class PlanModel:
    def json(self, instruction, payload):
        assert payload["topic"] == "風之旅人：陌生人的合作故事"
        return {"english_topic": "Journey anonymous cooperation", "game": "風之旅人",
                "queries_zh": ["風之旅人 合作 訪談", "風之旅人 開發者"],
                "queries_en": ["Journey developer cooperation interview", "Journey anonymous players design"],
                "footage_queries": ["Journey cooperation gameplay", "Journey multiplayer gameplay"]}


def test_arbitrary_chinese_topic_dynamic_translation():
    plan = plan_topic(PlanModel(), "風之旅人：陌生人的合作故事")
    assert "Journey" in plan["english_topic"]
    assert len(plan["queries_en"]) == 2


@pytest.fixture
def evidence():
    # These sentences are deliberately labeled fixtures, not asserted game facts.
    text = "Synthetic test evidence only. This is a fictional fixture sentence for citation validation."
    sources = [{"id": "S1", "url": "https://first.example.org/story", "text": text},
               {"id": "S2", "url": "https://second.example.net/story", "text": text}]
    claims = [{"id": f"C{i}", "statement": f"測試資料{i}，非真實研究", "date": None,
               "evidence": [{"source_id": "S1", "quote": text}, {"source_id": "S2", "quote": text}]} for i in range(4)]
    return sources, claims


def test_exact_quotes_required(evidence):
    sources, claims = evidence
    assert len(validate_claims(claims, sources)) == 4
    claims[0]["evidence"][0]["quote"] = "Invented citation that is absent from the actual retrieved page"
    with pytest.raises(Blocked) as exc:
        validate_claims(claims, sources)
    assert exc.value.code == "EVIDENCE_INVALID"


def test_wikipedia_languages_not_independent(evidence):
    sources, claims = evidence
    sources[0]["url"] = "https://en.wikipedia.org/wiki/Test"
    sources[1]["url"] = "https://zh.wikipedia.org/wiki/Test"
    with pytest.raises(Blocked) as exc:
        validate_claims(claims, sources)
    assert exc.value.code == "EVIDENCE_INSUFFICIENT"


def test_evidence_auditor_can_veto_syndication(evidence, tmp_path):
    sources, claims = evidence
    class FakeModel:
        calls = 0
        def json(self, instruction, payload):
            if "Select up to 3" in instruction:
                return {"quotes": [payload["source"]["text"]]}
            self.calls += 1
            if self.calls == 1: return {"claims": claims, "uncertainties": []}
            return {"claims": [{"id": c["id"], "supported": True, "independent_sources": False, "reason": "same syndicated fixture"} for c in claims]}
    with pytest.raises(Blocked) as exc:
        fact_check(FakeModel(), {"english_topic": "synthetic fixture"}, sources, tmp_path)
    assert exc.value.code == "FACT_CHECK_FAILED"
    assert (tmp_path / "evidence_audit.json").is_file()


def test_research_reads_bodies_not_headlines(tmp_path):
    body = "<html><body><article>" + "".join(f"<p>Paragraph {i}. This synthetic article has sufficient text to exercise article extraction. It is not a research result. The fixture tests body retrieval.</p>" for i in range(12)) + "</article></body></html>"
    class FakeWeb:
        def get(self, url, params=None):
            if params:
                return ("<rss><channel>" + "".join(f"<item><title>Unverified headline {i}</title><link>https://fixture{i}.example.org/article</link></item>" for i in range(3)) + "</channel></rss>").encode(), url
            return body.encode(), url
    sources = research(FakeWeb(), {"queries_zh": ["測試"], "queries_en": ["fixture"]}, tmp_path)
    assert len(sources) == 3
    assert all("synthetic article" in s["text"] and "Unverified headline" not in s["text"] for s in sources)


def test_headlines_alone_cannot_pass(tmp_path):
    class EmptyWeb:
        def get(self, *args): return b"<rss><channel/></rss>", args[0]
    with pytest.raises(Blocked) as exc:
        research(EmptyWeb(), {"queries_zh": ["測試"], "queries_en": []}, tmp_path)
    assert exc.value.code == "RESEARCH_INSUFFICIENT"
    assert json.loads((tmp_path / "research.json").read_text())["sources"] == []


def script_fixture():
    return {"scenes": [{"narration": f"第{i}段測試。" + "這只是合成測試文字，用於驗證程式門檻。"*5,
            "claim_ids": ["C0"], "visual_need": "fictional test gameplay", "footage_queries": ["test gameplay"]} for i in range(20)]}


def test_script_requires_citations_and_duration(evidence):
    _, claims = evidence
    script = validate_script(script_fixture(), {"claims": claims}, 10)
    assert script["scenes"][0]["info"] == "資料：C0"
    script["scenes"][3]["claim_ids"] = ["hallucinated"]
    with pytest.raises(Blocked) as exc:
        validate_script(script, {"claims": claims}, 10)
    assert exc.value.code == "SCRIPT_UNGROUNDED"


def test_script_repetition_rejected(evidence):
    _, claims = evidence
    script = script_fixture()
    script["scenes"][1]["narration"] = script["scenes"][0]["narration"]
    with pytest.raises(Blocked) as exc:
        validate_script(script, {"claims": claims}, 10)
    assert exc.value.code == "SCRIPT_REPETITIVE"


def commons_fixture(license_name="CC BY 4.0"):
    return {"title": "File:Synthetic.webm", "imageinfo": [{"url": "https://upload.wikimedia.org/synthetic.webm", "descriptionurl": "https://commons.wikimedia.org/wiki/File:Synthetic.webm", "size": 200000,
        "extmetadata": {"LicenseShortName": {"value": license_name}, "LicenseUrl": {"value": "https://creativecommons.org/licenses/by/4.0/"}, "Artist": {"value": "Fixture Author"}}}]}


@pytest.mark.parametrize("license_name", ["CC BY-NC 4.0", "CC BY-ND 4.0", "CC BY-SA 4.0", "fair use", "CC BY 4.0 or noncommercial only", ""])
def test_restrictive_licenses_rejected(license_name):
    assert licensed_record(commons_fixture(license_name)) is None


def test_commons_requires_rights_evidence():
    page = commons_fixture()
    assert licensed_record(page)["creator"] == "Fixture Author"
    page["imageinfo"][0]["extmetadata"]["Restrictions"] = {"value": "copyright permission required"}
    assert licensed_record(page) is None


def test_conflicting_license_url_rejected():
    page = commons_fixture()
    page["imageinfo"][0]["extmetadata"]["LicenseUrl"]["value"] = "https://creativecommons.org/licenses/by-nc/4.0/"
    assert licensed_record(page) is None


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    work = tmp_path_factory.mktemp("synthetic-media")
    cuts = work / "cuts.mp4"
    command(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=red:s=320x180:r=24:d=4", "-f", "lavfi", "-i", "color=blue:s=320x180:r=24:d=4", "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-c:v", "libx264", "-threads", "2", cuts])
    moving = work / "moving.mp4"
    command(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=24:d=6", "-c:v", "libx264", "-threads", "2", moving])
    sound = work / "sound.wav"
    command(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=24000:duration=3", sound])
    return work, cuts, moving, sound


def test_actual_scene_detection(media):
    _, cuts, _, _ = media
    shots = detect_shots(cuts)
    assert len(shots) == 2
    assert shots[0]["end"] == pytest.approx(4, abs=0.1)
    assert shots[1]["start"] == pytest.approx(4, abs=0.1)
    assert all(0 < s["end"]-s["start"] <= 8 for s in shots)


def test_visual_matching_uses_frames_and_never_repeats(media, tmp_path, monkeypatch):
    _, cuts, _, _ = media
    class FakeVision:
        def json(self, instruction, payload, images):
            assert len(images) == 3 and all(Path(p).stat().st_size > 100 for p in images)
            return {"gameplay": True, "correct_game": True, "event_visible": True, "confidence": 0.95, "observations": "synthetic fixture only", "reason": "test mechanics"}
    library = Library(None, FakeVision(), tmp_path)
    monkeypatch.setattr(library, "search", lambda queries: None)
    library.shots = [{**s, "id": str(i), "asset_id": "synthetic", "path": str(cuts)} for i,s in enumerate(detect_shots(cuts))]
    scene = {"id": 1, "visual_need": "synthetic", "narration": "測試", "footage_queries": ["fixture"]}
    assert len(library.match(scene, 7)) == 2
    with pytest.raises(Blocked) as exc:
        library.match({**scene, "id": 2}, 3)
    assert exc.value.code == "LICENSED_RELEVANT_FOOTAGE_MISSING"


def test_vision_rejection_blocks_render(media, tmp_path, monkeypatch):
    class Reject:
        def json(self, *args): return {"gameplay": False, "confidence": 1.0}
    library = Library(None, Reject(), tmp_path)
    monkeypatch.setattr(library, "search", lambda q: None)
    library.shots = [{"id": "fixture", "asset_id": "fixture", "start": 0, "end": 4, "path": str(media[2])}]
    with pytest.raises(Blocked) as exc:
        library.match({"id":1, "footage_queries":[], "visual_need":"unrelated", "narration":"測試"}, 3)
    assert exc.value.code == "LICENSED_RELEVANT_FOOTAGE_MISSING"


def test_real_1080p_render_subtitles_thumbnail_and_decode(media, tmp_path):
    _, _, moving, sound = media
    seconds = duration(sound)
    cues = [{"start": 0.1, "end": 2.8, "text": "繁體中文字幕：合成測試，非遊戲成品。"}]
    scene = {"id": 1, "info": "資料：合成測試", "narration": cues[0]["text"]}
    candidate, full_cues = render({"scenes": [scene]}, [{"path":str(sound), "seconds":seconds, "cues":cues}],
        [[{"path":str(moving), "start":0, "end":seconds}]], tmp_path)
    qa = inspect_media(candidate, seconds, full_cues, min_seconds=2, max_seconds=5)
    assert qa["passed"], qa
    assert qa["full_decode"] and qa["caption_cues"] == 1
    assert "繁體中文字幕" in (tmp_path / "documentary.srt").read_text()
    thumb = tmp_path / "thumbnail.jpg"
    thumbnail(candidate, "合成測試：不是遊戲紀錄片", thumb)
    from PIL import Image
    assert Image.open(thumb).size == (1280,720)
    # Duration policy stays strict for production, even when technical tests use a short fixture.
    assert not inspect_media(candidate, seconds, full_cues)["passed"]


def test_blank_silent_output_fails_qa(tmp_path):
    path = tmp_path / "bad.mp4"
    command(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=black:s=1920x1080:r=24:d=4", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "4", "-c:v", "libx264", "-threads", "2", "-preset", "ultrafast", "-c:a", "aac", path])
    qa = inspect_media(path, 4, [{"start":0, "end":4, "text":"測試字幕"}], min_seconds=2, max_seconds=5)
    assert not qa["passed"]
    assert "Long black interval detected" in qa["failures"]
    assert "Narration silence exceeds three seconds" in qa["failures"]


@pytest.mark.parametrize("cues", [[{"start":0,"end":2,"text":"一"},{"start":1,"end":3,"text":"二"}], [{"start":0,"end":9,"text":"太長"}], [{"start":0,"end":0.1,"text":"字幕快得無法閱讀"}]])
def test_bad_caption_timing_rejected(cues):
    with pytest.raises(Blocked): validate_cues(cues, 10)


def test_ass_text_cannot_inject_effects(tmp_path):
    path = tmp_path / "safe.ass"
    ass_file(path, [{"start":0,"end":2,"text":r"{\pos(0,0)}測試"}], 3, "來源")
    assert r"{\pos" not in path.read_text()


def test_real_cli_missing_credentials_fails_and_writes_report(tmp_path, monkeypatch):
    for k in ("LLM_API_KEY", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    assert main(["--topic", "寶可夢紅綠版，推卡車抓夢幻的都市傳說", "--out", str(tmp_path)]) == 2
    reports = list(tmp_path.glob("*/qa_report.json"))
    assert len(reports) == 1
    report = json.loads(reports[0].read_text())
    assert report["blocker"]["code"] == "MODEL_CREDENTIAL_REQUIRED"
    assert not list(tmp_path.rglob("*.mp4"))


def test_existing_output_never_reused(tmp_path):
    with pytest.raises(FileExistsError):
        run_pipeline("測試", 12, tmp_path)


def test_batch_collects_all_blockers(tmp_path, monkeypatch):
    for k in ("LLM_API_KEY", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    topics = tmp_path / "topics.json"
    topics.write_text(json.dumps(["題材甲", "題材乙"]))
    assert main(["--topics-file", str(topics), "--out", str(tmp_path/"out")]) == 2
    assert len(list((tmp_path/"out").glob("*/qa_report.json"))) == 2


def test_missing_licensed_assets_stops_before_voice_or_render(tmp_path, monkeypatch):
    import documentary.pipeline as pipeline
    monkeypatch.setattr(pipeline, "plan_topic", lambda *a: {"footage_queries": ["fixture"]})
    monkeypatch.setattr(pipeline, "research", lambda *a: [{"id":"fixture"}])
    monkeypatch.setattr(pipeline, "fact_check", lambda *a: {"claims": []})
    monkeypatch.setattr(pipeline, "write_script", lambda *a: {"scenes": []})
    def forbidden(*args, **kwargs):
        pytest.fail("No voice/render may run when there are no licensed assets")
    monkeypatch.setattr(pipeline, "synthesize", forbidden)
    monkeypatch.setattr(pipeline, "render", forbidden)
    class NoAssets:
        records = []
        def __init__(self, *a): pass
        def search(self, queries): pass
    monkeypatch.setattr(pipeline, "Library", NoAssets)
    out = tmp_path / "blocked"
    report = run_pipeline("合成測試", 12, out, model=object(), web=object())
    assert report["status"] == "BLOCKED"
    assert report["blocker"]["code"] == "LICENSED_GAMEPLAY_MISSING"
    assert report["completed_stages"] == ["bilingual_topic_expansion", "research", "evidence_audit", "original_script"]
    assert not list(out.rglob("*.mp4"))
