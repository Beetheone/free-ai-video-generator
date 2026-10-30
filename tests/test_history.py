"""Synthetic fixtures test mechanics of the history mode only; they are NEVER real research or archive images."""
import json
import subprocess
import wave
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from documentary import history, youtube
from documentary.core import Blocked, command, duration
from documentary.history import (ImagePool, assign_images, build_timeline, chip_for, license_kind, licensed_media_record,
                                 pick_music, plan_history)
from documentary.history_pipeline import run_history
from documentary.history_render import history_thumbnail, render_scene, split_frames


# ------------------------------------------------------------------ fixtures

def page(i, *, license_name="Public domain", mime="image/jpeg", width=1600, height=900, artist="Fixture Author", restrictions="",
         host="upload.wikimedia.org", categories="", title=None):
    meta = {"LicenseShortName": {"value": license_name}, "Artist": {"value": artist}, "LicenseUrl": {"value": ""},
            "Restrictions": {"value": restrictions}, "Categories": {"value": categories}, "ImageDescription": {"value": f"fixture {i}"}}
    if license_name.lower().startswith("cc by"):
        meta["LicenseUrl"]["value"] = "https://creativecommons.org/licenses/by/" + license_name.split()[-1] + "/"
    return {"title": title or f"File:Fixture{i}.jpg",
            "imageinfo": [{"url": f"https://{host}/fixture/{i}.jpg", "thumburl": f"https://{host}/fixture/{i}.jpg", "size": 200_000,
                           "width": width, "height": height, "mime": mime,
                           "descriptionurl": f"https://commons.wikimedia.org/wiki/File:Fixture{i}.jpg", "extmetadata": meta}]}


def jpeg(color):
    buf = BytesIO()
    Image.new("RGB", (1600, 900), color).save(buf, "JPEG")
    return buf.getvalue()


class FakeWeb:
    def __init__(self, pages_per_query=4, total=40):
        self.pages_per_query, self.total, self.counter = pages_per_query, total, 0
        self.gets = []

    def json(self, url, params=None):
        params = params or {}
        if "wikipedia.org" in url:
            return {"query": {"pages": {"1": {"images": [{"title": "File:Seed1.jpg"}, {"title": "File:Seed2.svg"}]}}}}
        if params.get("titles"):
            return {"query": {"pages": {"1": page(900, title="File:Seed1.jpg")}}}
        pages = {}
        for _ in range(self.pages_per_query):
            if self.counter < self.total:
                self.counter += 1
                pages[str(self.counter)] = page(self.counter)
        return {"query": {"pages": pages}}

    def get(self, url, params=None, limit=3_000_000):
        self.gets.append(url)
        n = int(url.rsplit("/", 1)[1].split(".")[0])
        return jpeg(((n * 37) % 200 + 40, (n * 91) % 200 + 40, (n * 53) % 200 + 40)), url


class FakeModel:
    name = "fixture-model"

    def __init__(self, *, graphic_ids=(), plan=None):
        self.calls, self.usage, self.usage_unavailable_calls = 0, {"prompt_tokens": 0, "completion_tokens": 0}, 0
        self.graphic_ids, self.plan = set(graphic_ids), plan

    def json(self, instruction, payload, images=()):
        self.calls += 1
        if "Translate and disambiguate this history topic" in instruction:
            return self.plan or {"english_topic": "Fixture War", "era": "1930s fixture", "queries_zh": ["測試戰爭", "測試戰爭 史料"],
                    "queries_en": ["fixture war", "fixture war history"], "image_queries": ["fixture war", "fixture soldiers", "fixture map"],
                    "reference_titles_en": ["Fixture War"], "candidate_urls": []}
        if "Inspect these actual images" in instruction:
            return {"images": [{"id": i["id"], "depicts": "a fixture picture", "kind": "photograph", "relevance": 0.9, "impact": 0.5 + n / 100,
                                "graphic": i["id"] in self.graphic_ids, "modern_overlay": False} for n, i in enumerate(payload["images"])]}
        if "Choose images for each narrated scene" in instruction:
            ids = [c["id"] for c in payload["candidates"]]
            return {"scenes": [{"id": s["id"], "images": [{"id": ids[(s["id"] * 2 + k) % len(ids)], "fit": "direct", "confidence": 0.9} for k in range(2)]}
                               for s in payload["scenes"]]}
        if "opening hook" in instruction:
            return {"opens_with_outcome_or_paradox": True, "has_open_question": True, "no_greeting_or_preamble": True,
                    "supported_by_claims": True, "reason": "fixture"}
        if "Write packaging" in instruction:
            return {"title": "合成測試：一場荒謬的戰爭", "thumbnail_text": "荒謬戰爭", "intro": "這是合成測試的簡介，只驗證程式流程，沒有真實內容。",
                    "tags": ["歷史", "測試", "冷知識"]}
        if '"supported":bool,"misleading":bool' in instruction:
            return {"supported": True, "misleading": False, "reason": "fixture"}
        raise AssertionError("unexpected instruction: " + instruction[:80])


def tone(path, seconds):
    command(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency=330:duration={seconds}", "-ar", "48000", "-ac", "1", path])


def fake_deps(scene_seconds=4):
    claims = [{"id": "C1", "statement": "合成主張一", "date": "1932-11", "evidence": [{"source_id": "S1", "quote": "fixture"}]},
              {"id": "C2", "statement": "合成主張二", "date": None, "evidence": [{"source_id": "S1", "quote": "fixture"}]}]
    sources = [{"id": "S1", "title": "Fixture source", "url": "https://fixture.example.org/a", "text": "fixture text"}]

    def write_script(model, plan, ledger, minutes, out, *, sections=None, instruction=None, **_):
        assert sections and instruction and sections[0].startswith("開場鉤子")
        scenes = [{"id": i + 1, "narration": f"這是第{i+1}段合成測試旁白，只驗證程式流程。", "claim_ids": ["C1" if i % 2 == 0 else "C2"],
                   "visual_need": "fixture image", "footage_queries": [f"fixture scene {i}"], "info": "資料：C1", "chapter": i * 6 // 8}
                  for i in range(8)]
        script = {"title": "合成測試", "scenes": scenes}
        (out / "script.json").write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
        return script

    def synthesize(text, dest, engine="edge", voice="x"):
        wav = Path(dest).with_suffix(".wav")
        tone(wav, scene_seconds)
        return {"path": str(wav), "seconds": duration(wav), "cues": [{"start": 0.0, "end": duration(wav) - 0.1, "text": text[:20]}],
                "timing_method": "fixture"}

    from documentary.production import inspect_media
    return SimpleNamespace(research=lambda web, plan, out, **kw: sources, fact_check=lambda *a, **kw: {"claims": claims, "timeline": []},
                           plan_repair=None, write_script=write_script, synthesize=synthesize, inspect_media=inspect_media)


# ------------------------------------------------------------------ licenses

@pytest.mark.parametrize("name,expected", [("CC0", "pd"), ("Public domain", "pd"), ("PD-old-100", "pd"), ("PD US Government", "pd"),
                                           ("CC BY 4.0", "by"), ("CC BY 2.0", "by"), ("CC BY-SA 4.0", None), ("CC BY-NC 4.0", None),
                                           ("CC BY-ND 3.0", None), ("Fair use", None), ("Non-free media", None), ("", None), ("GFDL", None)])
def test_license_kind(name, expected):
    assert license_kind(name) == expected


def test_media_record_accepts_good_and_rejects_bad():
    assert licensed_media_record(page(1))["license_kind"] == "pd"
    assert licensed_media_record(page(2, license_name="CC BY 4.0"))["license_kind"] == "by"
    for bad in (page(3, license_name="CC BY-SA 4.0"), page(4, restrictions="trademark"), page(5, width=500, height=300),
                page(6, mime="image/svg+xml"), page(7, host="example.com"), page(8, license_name="CC BY 4.0", artist="")):
        assert licensed_media_record(bad) is None


# ------------------------------------------------------------------ pool & assignment

def test_pool_downloads_dedupes_and_credits(tmp_path):
    web = FakeWeb(pages_per_query=3, total=6)
    pool = ImagePool(web, FakeModel(), tmp_path, delay=0)
    pool.seed_from_articles(["Fixture War"])
    pool.search(["a", "b", "a"])
    assert len(pool.records) == 1 + 6  # one article image + six distinct search images; repeated query ignored
    assert all(Path(r["path"]).is_file() and Path(r["preview"]).is_file() for r in pool.records)
    assert (tmp_path / "image_sources.json").is_file()


def test_vision_tags_exclude_graphic_images(tmp_path):
    web = FakeWeb(pages_per_query=8, total=8)
    pool = ImagePool(web, FakeModel(), tmp_path, delay=0)
    pool.search(["a"])
    pool.model = FakeModel(graphic_ids={pool.records[0]["id"]})
    pool.tag({"original_topic": "x"})
    assert len(pool.usable) == len(pool.records) - 1
    assert not pool.records[0]["tags"]["usable"]


def scenes(n):
    return [{"id": i + 1, "narration": f"第{i+1}段", "visual_need": "x", "footage_queries": ["q"], "claim_ids": ["C1"]} for i in range(n)]


def usable_pool(tmp_path, count):
    pool = ImagePool(FakeWeb(pages_per_query=count, total=count), FakeModel(), tmp_path, delay=0)
    pool.search(["a"])
    pool.tag({"original_topic": "x"})
    return pool


def test_too_few_images_blocks_without_stand_ins(tmp_path):
    pool = usable_pool(tmp_path, 5)
    with pytest.raises(Blocked) as exc:
        assign_images(FakeModel(), {}, scenes(4), pool, tmp_path)
    assert exc.value.code == "VISUALS_INSUFFICIENT"


def test_assignment_ignores_unknown_ids_and_low_confidence(tmp_path):
    pool = usable_pool(tmp_path, 10)
    real = pool.usable[0]["id"]

    class Model(FakeModel):
        def json(self, instruction, payload, images=()):
            return {"scenes": [{"id": 1, "images": [{"id": "nope", "fit": "direct", "confidence": 0.99},
                                                    {"id": real, "fit": "direct", "confidence": 0.2},
                                                    {"id": real, "fit": "context", "confidence": 0.7}]}]}
    chosen = assign_images(Model(), {}, scenes(1), pool, tmp_path)
    assert chosen[1] == [{"id": real, "fit": "context", "confidence": 0.7}]


def test_timeline_covers_exact_seconds_without_adjacent_repeats(tmp_path):
    pool = usable_pool(tmp_path, 12)
    sc = scenes(6)
    secs = [7.3, 14.0, 4.1, 20.5, 9.9, 2.0]
    timeline = build_timeline(sc, secs, {}, pool)
    for shots, length in zip(timeline, secs):
        assert shots and abs(sum(s["seconds"] for s in shots) - length) < 1e-9
        assert all(2.0 <= s["seconds"] <= 10 for s in shots)
    flat = [s["asset_id"] for shots in timeline for s in shots]
    assert all(a != b for a, b in zip(flat, flat[1:]))


def test_chip_uses_only_cited_claim_dates():
    claims = {"C1": {"date": "1932-11-02"}, "C2": {"date": None}, "C3": {"date": "1950"}}
    assert chip_for({"claim_ids": ["C3", "C1"]}, claims) == "1932年11月2日"
    assert chip_for({"claim_ids": ["C2"]}, claims) == ""
    assert chip_for({"claim_ids": ["C3"]}, claims) == "1950年"


def test_plan_requires_image_queries():
    class Bad(FakeModel):
        def json(self, instruction, payload, images=()):
            return {"english_topic": "x", "queries_zh": ["a", "b"], "queries_en": ["a", "b"], "image_queries": [], "reference_titles_en": [], "candidate_urls": []}
    with pytest.raises(Blocked) as exc:
        plan_history(Bad(), "題目")
    assert exc.value.code == "MODEL_SCHEMA"


# ------------------------------------------------------------------ rendering

def test_split_frames_cover_audio():
    for secs in ([4.0], [2.0, 3.5, 1.2]):
        frames = split_frames(secs, sum(secs))
        assert sum(frames) >= sum(secs) * 24 and all(f >= 1 for f in frames)


def test_real_ken_burns_scene_render(tmp_path):
    images = []
    for i, size in enumerate(((1600, 900), (800, 1200))):  # landscape and portrait
        path = tmp_path / f"i{i}.jpg"
        Image.new("RGB", size, (180, 90 + i * 40, 60)).save(path)
        images.append(path)
    audio = tmp_path / "a.wav"
    tone(audio, 3)
    shots = [{"path": str(p), "seconds": 1.5, "motion": m, "asset_id": str(i)} for i, (p, m) in enumerate(zip(images, ("zoom_in", "pan_left")))]
    work = tmp_path / "work"
    work.mkdir()
    clip = render_scene({"id": 1}, {"seconds": duration(audio), "cues": [{"start": 0, "end": 2.5, "text": "測試字幕"}]}, shots, work, "1932年11月")
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", clip], capture_output=True, text=True).stdout)
    video = info["streams"][0]
    assert (video["width"], video["height"], video["codec_name"]) == (1920, 1080, "h264")
    assert abs(duration(clip) - duration(audio)) < 0.1


def test_thumbnail_is_16_9_jpeg(tmp_path):
    src = tmp_path / "s.jpg"
    Image.new("RGB", (900, 1200), (120, 140, 160)).save(src)
    history_thumbnail(src, "荒謬戰爭", tmp_path / "t.jpg")
    assert Image.open(tmp_path / "t.jpg").size == (1280, 720)


# ------------------------------------------------------------------ whole pipeline

def test_full_pipeline_with_synthetic_services(tmp_path):
    out = tmp_path / "run"
    report = run_history("合成測試題目", 10, out, model=FakeModel(), web=FakeWeb(), deps=fake_deps(), bounds=(5, 200), pool_delay=0)
    assert report["status"] == "COMPLETE_AUTOMATED_CHECKS", report.get("blocker")
    for name in ("documentary.mp4", "documentary.srt", "thumbnail.jpg", "DESCRIPTION.txt", "ATTRIBUTION.md", "packaging.json", "PROGRESS.md"):
        assert (out / name).is_file(), name
    assert abs(duration(out / "documentary.mp4") - 32) < 0.5
    description = (out / "DESCRIPTION.txt").read_text(encoding="utf-8")
    assert "AI 輔助" in description and "章節" in description and "0:00 開場" in description
    assert report["hook_audit"]["passed"] is True


def test_pipeline_blocks_without_images_and_releases_no_video(tmp_path):
    out = tmp_path / "run"
    report = run_history("合成測試題目", 10, out, model=FakeModel(), web=FakeWeb(total=0), deps=fake_deps(), bounds=(5, 200), pool_delay=0)
    assert report["status"] == "BLOCKED" and report["blocker"]["code"] == "VISUALS_INSUFFICIENT"
    assert report["failed_stage"] == "image_pool"
    assert not list(out.rglob("*.mp4")) and not (out / "audio").exists()


def test_script_milestone_stops_before_images(tmp_path):
    report = run_history("合成測試題目", 12, tmp_path / "run", model=FakeModel(), web=FakeWeb(), deps=fake_deps(), stop_after="script", pool_delay=0)
    assert report["status"] == "SCRIPT_READY"
    assert not (tmp_path / "run" / "images").exists()


def test_runtime_outside_range_blocks(tmp_path):
    report = run_history("合成測試題目", 10, tmp_path / "run", model=FakeModel(), web=FakeWeb(), deps=fake_deps(), bounds=(600, 900), pool_delay=0)
    assert report["blocker"]["code"] == "NARRATION_RUNTIME"


@pytest.mark.parametrize("minutes", [9, 16])
def test_minutes_out_of_range_rejected(tmp_path, minutes):
    report = run_history("題目", minutes, tmp_path / "run", model=FakeModel(), web=FakeWeb(), deps=fake_deps(), pool_delay=0)
    assert report["blocker"]["code"] == "INPUT_INVALID"


# ------------------------------------------------------------------ music & upload

def test_music_requires_license_and_instrumental_hint(tmp_path):
    def audio_page(i, title, license_name="CC BY 4.0", categories="Instrumental music"):
        p = page(i, license_name=license_name, title=title, categories=categories)
        p["imageinfo"][0].update(mime="audio/ogg", url=f"https://upload.wikimedia.org/fixture/{i}.ogg")
        p["imageinfo"][0].pop("thumburl")
        p["imageinfo"][0].pop("width"), p["imageinfo"][0].pop("height")
        return p

    class Web:
        def json(self, url, params=None):
            return {"query": {"pages": {"1": audio_page(1, "File:Speech.ogg", categories="Speech recordings"),
                                        "2": audio_page(2, "File:Theme.ogg", license_name="CC BY-SA 4.0"),
                                        "3": audio_page(3, "File:Calm piano.ogg")}}}

        def get(self, url, params=None, limit=0):
            return b"OggS fixture", url
    record = pick_music(Web(), tmp_path, delay=0)
    assert record["title"] == "File:Calm piano.ogg" and Path(record["path"]).is_file() and record["license_kind"] == "by"


def test_music_none_when_nothing_qualifies(tmp_path):
    class Web:
        def json(self, url, params=None):
            return {"query": {"pages": {}}}
    assert pick_music(Web(), tmp_path, delay=0) is None


def test_youtube_metadata_is_private_and_disclosed():
    meta = youtube.metadata("標題", "說明", ["a", "", "b"])
    assert meta["status"] == {"privacyStatus": "private", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}
    assert meta["snippet"]["tags"] == ["a", "b"]


def test_youtube_upload_requires_secrets(monkeypatch):
    for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(youtube.UploadError, match="Missing secrets"):
        youtube.access_token()


def test_youtube_resumable_flow(tmp_path, monkeypatch):
    for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
        monkeypatch.setenv(k, "x")
    video = tmp_path / "v.mp4"
    video.write_bytes(b"0" * 100)
    thumb = tmp_path / "t.jpg"
    thumb.write_bytes(b"1")

    class Resp:
        def __init__(self, status, body=None, headers=None):
            self.status_code, self._body, self.headers = status, body or {}, headers or {}
        def json(self):
            return self._body

    class Session:
        def __init__(self):
            self.sent = []
        def post(self, url, **kw):
            self.sent.append(url)
            if url == youtube.TOKEN_URL:
                return Resp(200, {"access_token": "tok"})
            if url == youtube.UPLOAD_URL:
                assert json.loads(kw["data"])["status"]["privacyStatus"] == "private"
                return Resp(200, headers={"Location": "https://upload.example/session"})
            return Resp(403)  # thumbnail refused: video upload must still count as success
        def put(self, url, **kw):
            return Resp(200, {"id": "abc123"})
    outcome = youtube.upload(video, "t", "d", ["x"], thumb, session=Session())
    assert outcome["video_id"] == "abc123" and outcome["privacy"] == "private" and outcome["thumbnail"].startswith("not set")


# ------------------------------------------------------------------ voice probe

def test_voice_probe_reports_http_status_without_leaking_urls(monkeypatch):
    import sys
    import types
    from documentary import voice_probe

    class Communicate:
        def __init__(self, *a, **kw):
            pass
        async def stream(self):
            raise RuntimeError("403, message='Invalid response status', url='wss://secret.example/?Token=abc'")
            yield
    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(Communicate=Communicate))
    ok, detail = voice_probe.probe(timeout=5)
    assert ok is False and detail == "RuntimeError HTTP 403" and "secret" not in detail


def test_voice_probe_success(monkeypatch):
    import sys
    import types
    from documentary import voice_probe

    class Communicate:
        def __init__(self, *a, **kw):
            pass
        async def stream(self):
            yield {"type": "audio", "data": b"x"}
    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(Communicate=Communicate))
    assert voice_probe.probe(timeout=5) == (True, "audio received")


# ------------------------------------------------------------------ Internet Archive footage

def make_mp4(path, seconds=24):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size=640x480:rate=24:duration={seconds}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)
    return Path(path).read_bytes()


@pytest.mark.parametrize("url,expected", [
    ("https://creativecommons.org/publicdomain/zero/1.0/", ("pd", "CC0 1.0")),
    ("http://creativecommons.org/publicdomain/mark/1.0/", ("pd", "Public Domain Mark 1.0")),
    ("https://creativecommons.org/licenses/by/4.0/", ("by", "CC BY 4.0")),
    ("https://creativecommons.org/licenses/by-sa/4.0/", None),
    ("https://creativecommons.org/licenses/by-nc/4.0/", None),
    ("https://creativecommons.org/licenses/by-nd/3.0/", None),
    ("", None), (None, None), ("https://example.com/license", None),
])
def test_archive_license_allowlist(url, expected):
    from documentary.history_footage import archive_license
    assert archive_license(url) == expected


def test_pick_file_prefers_h264_mp4_within_budget():
    from documentary.history_footage import pick_file
    files = [{"name": "a.ogv", "format": "Ogg Video", "size": "5000000"},
             {"name": "a.mp4", "format": "h.264", "size": "9000000"},
             {"name": "huge.mp4", "format": "h.264", "size": "900000000"},
             {"name": "dir/x.mp4", "format": "h.264", "size": "9000000"},
             {"name": "tiny.mp4", "format": "h.264", "size": "10"}]
    assert pick_file(files) == "a.mp4"
    assert pick_file([{"name": "x.mkv", "format": "Matroska", "size": "5000000"}]) is None


class ArchiveWeb:
    def __init__(self, mp4, license_url="https://creativecommons.org/publicdomain/mark/1.0/", creator="Film Unit"):
        self.mp4, self.license_url, self.creator, self.gets = mp4, license_url, creator, []

    def json(self, url, params=None):
        if "advancedsearch" in url:
            return {"response": {"docs": [{"identifier": "good_film", "title": "Good", "licenseurl": self.license_url},
                                           {"identifier": "no_license", "title": "Nope"},
                                           {"identifier": "nc_film", "licenseurl": "https://creativecommons.org/licenses/by-nc/4.0/"}]}}
        assert url.endswith("/good_film")
        return {"metadata": {"title": "Good film", "licenseurl": self.license_url, "creator": self.creator, "description": "<p>A film</p>"},
                "files": [{"name": "good_film.mp4", "format": "h.264", "size": str(len(self.mp4))}]}

    def get(self, url, params=None, limit=3_000_000):
        self.gets.append(url)
        return self.mp4, url


def test_footage_collect_cuts_licensed_clips_into_the_pool(tmp_path):
    from documentary.history_footage import collect
    web = ArchiveWeb(make_mp4(tmp_path / "src.mp4"))
    pool = ImagePool(web, FakeModel(), tmp_path, delay=0)
    report = collect(web, pool, {"english_topic": "Emu War 1932", "image_queries": ["emu soldiers"]}, tmp_path, delay=0)
    assert report["clips"] >= 2 and [i["id"] for i in report["items"]] == ["good_film"]
    assert all("good_film" in g for g in web.gets)  # unlicensed and NC items were never downloaded
    rec = pool.records[0]
    assert rec["media"] == "video" and rec["license_kind"] == "pd" and rec["source_url"] == "https://archive.org/details/good_film"
    assert all(Path(r[k]).is_file() for r in pool.records for k in ("path", "preview", "still"))
    assert 2 <= duration(rec["path"]) <= 8.5
    assert (tmp_path / "footage_sources.json").is_file()
    assert not list((tmp_path / "footage").glob("*.mp4"))  # the full download is deleted after cutting


def test_footage_requires_creator_for_cc_by(tmp_path):
    from documentary.history_footage import collect
    web = ArchiveWeb(make_mp4(tmp_path / "s.mp4", 12), license_url="https://creativecommons.org/licenses/by/4.0/", creator="")
    pool = ImagePool(web, FakeModel(), tmp_path, delay=0)
    report = collect(web, pool, {"english_topic": "Emu"}, tmp_path, delay=0)
    assert report["clips"] == 0 and not web.gets and pool.records == []


def test_footage_failures_never_raise(tmp_path):
    from documentary.history_footage import collect
    class Broken:
        def json(self, *a, **k):
            raise Blocked("NETWORK", "archive.org: ConnectionError")
    pool = ImagePool(Broken(), FakeModel(), tmp_path, delay=0)
    report = collect(Broken(), pool, {"english_topic": "Emu"}, tmp_path, delay=0)
    assert report["clips"] == 0 and report["errors"]


def test_real_video_shot_renders_with_images(tmp_path):
    from documentary.history_footage import make_clips
    src = tmp_path / "src.mp4"
    make_mp4(src, 12)
    clips = make_clips(str(src), "k", tmp_path)
    assert clips
    still = tmp_path / "i.jpg"
    Image.new("RGB", (1600, 900), (200, 80, 60)).save(still)
    audio = tmp_path / "a.wav"
    tone(audio, 6)
    shots = [{"path": str(still), "seconds": 2.0, "motion": "zoom_in", "asset_id": "i"},
             {"path": clips[0]["path"], "seconds": 4.0, "motion": "zoom_in", "asset_id": clips[0]["id"], "media": "video"}]
    work = tmp_path / "work"
    work.mkdir()
    out = render_scene({"id": 1}, {"seconds": duration(audio), "cues": [{"start": 0, "end": 2.5, "text": "測試字幕"}]}, shots, work, "")
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", out], capture_output=True, text=True).stdout)["streams"][0]
    assert (info["width"], info["height"]) == (1920, 1080)
    assert abs(duration(out) - duration(audio)) < 0.15


def test_clips_are_used_once_as_filler_and_description_credits_archive(tmp_path):
    pool = usable_pool(tmp_path, 6)
    clip = {"id": "clip1", "path": str(tmp_path / "c.mp4"), "media": "video", "license_kind": "pd", "license": "Public Domain Mark 1.0",
            "title": "Good film", "creator": "Film Unit", "source_url": "https://archive.org/details/good_film",
            "tags": {"usable": True, "relevance": 0.99, "impact": 0.9, "depicts": "soldiers", "kind": "other"}}
    pool.records.append(clip)
    sc = scenes(4)
    timeline = build_timeline(sc, [13.0] * 4, {}, pool)
    flat = [s for shots in timeline for s in shots]
    assert sum(1 for s in flat if s["asset_id"] == "clip1") == 1
    assert next(s for s in flat if s["asset_id"] == "clip1")["media"] == "video"
    pack = {"intro": "x"}
    text = history.description_text(pack, [(0.0, "開場")], [], [clip], None)
    assert "Internet Archive" in text and "good_film" in text
