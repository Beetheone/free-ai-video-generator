"""Real media/cancellation tests plus explicitly fake provider/policy fixtures."""
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

from documentary.core import Blocked, command, duration
from documentary.doctor import diagnose
from documentary.pipeline import run_pipeline
from documentary.production import edge_voice, inspect_media, render
from documentary.research import validate_claims


def test_original_caption_punctuation_and_english_spacing_survive(tmp_path, monkeypatch):
    text = "「寶可夢 Red／Green」，推卡車？這是測試！"
    class FakeTTS:
        def __init__(self, *args, **kwargs):
            assert kwargs["boundary"] == "WordBoundary"
        async def stream(self):
            yield {"type": "audio", "data": b"fake provider bytes; not speech"}
            for i, word in enumerate(["寶可夢", "Red", "Green", "推卡車", "這是測試"]):
                yield {"type":"WordBoundary", "offset":i*10_000_000, "duration":8_000_000, "text":word}
    monkeypatch.setattr("edge_tts.Communicate", FakeTTS)
    cues = asyncio.run(edge_voice(text, tmp_path / "fixture.mp3", "zh-TW-YunJheNeural"))
    assert "".join(c["text"] for c in cues) == text
    assert cues[0]["start"] == 0 and cues[-1]["end"] == 4.8


def test_tts_different_words_never_get_guessed_timings(tmp_path, monkeypatch):
    class WrongTTS:
        def __init__(self, *args, **kwargs): pass
        async def stream(self):
            yield {"type":"WordBoundary", "offset":0, "duration":10_000_000, "text":"不相符"}
    monkeypatch.setattr("edge_tts.Communicate", WrongTTS)
    with pytest.raises(Blocked) as exc:
        asyncio.run(edge_voice("正確原文", tmp_path / "fixture.mp3", "fixture"))
    assert exc.value.code == "CAPTION_TEXT_MISMATCH"


def test_media_timeout_is_a_specific_blocker():
    with pytest.raises(Blocked) as exc:
        command([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.05)
    assert exc.value.code == "MEDIA_TIMEOUT"


def test_invalid_model_config_still_writes_report(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_MAX_CALLS", "not-a-number")
    report = run_pipeline("測試", 12, tmp_path / "run")
    assert report["status"] == "BLOCKED"
    assert report["blocker"]["code"] == "MODEL_CONFIG"
    assert report["next_actions"]
    assert json.loads((tmp_path / "run/qa_report.json").read_text())["current_stage"] == "preflight"


def test_checkpoint_written_before_model_and_cancellation(tmp_path):
    out = tmp_path / "run"
    class InterruptedModel:
        def json(self, *args):
            checkpoint = json.loads((out / "qa_report.json").read_text())
            assert checkpoint["status"] == "RUNNING"
            assert checkpoint["current_stage"] == "bilingual_topic_expansion"
            raise KeyboardInterrupt
    report = run_pipeline("測試", 12, out, model=InterruptedModel(), web=object())
    assert report["status"] == "CANCELLED"
    assert report["failed_stage"] == "bilingual_topic_expansion"
    assert report["blocker"]["code"] == "RUN_INTERRUPTED"
    assert not list(out.rglob("*.mp4"))


def test_narration_checkpoint_survives_interruption(tmp_path, monkeypatch):
    import documentary.pipeline as pipeline
    out = tmp_path / "run"
    monkeypatch.setattr(pipeline, "plan_topic", lambda *a: {"footage_queries":[]})
    monkeypatch.setattr(pipeline, "research", lambda *a: [])
    monkeypatch.setattr(pipeline, "fact_check", lambda *a: {})
    monkeypatch.setattr(pipeline, "write_script", lambda *a: {"scenes":[{"id":1,"narration":"合成測試甲"},{"id":2,"narration":"合成測試乙"}]})
    class FakeLibrary:
        records = [{}]
        def __init__(self, *a): pass
        def search(self, *a): pass
    monkeypatch.setattr(pipeline, "Library", FakeLibrary)
    def interrupted(text, *args):
        if text.endswith("乙"):
            persisted = json.loads((out / "qa_report.json").read_text())
            assert persisted["current_stage"] == "narration"
            assert persisted["progress"] == {"completed":1, "total":2}
            raise InterruptedError
        return {"seconds":1, "cues":[], "path":"fake; not a real voice"}
    monkeypatch.setattr(pipeline, "synthesize", interrupted)
    report = run_pipeline("測試",12,out,model=object(),web=object())
    assert report["status"] == "CANCELLED"
    assert "licensed_footage_discovery" in report["completed_stages"]
    assert "narration" not in report["completed_stages"]
    assert report["progress"]["completed"] == 1


@pytest.mark.skipif(os.name != "posix", reason="SIGTERM integration uses POSIX signals")
def test_real_sigterm_finalizes_child_report(tmp_path):
    out, marker = tmp_path / "runs", tmp_path / "model-entered"
    script = tmp_path / "child.py"
    root = Path(__file__).resolve().parents[1]
    script.write_text("""import pathlib, sys, time
sys.path.insert(0, sys.argv[1])
import documentary.pipeline as p
class SlowModel:
    def json(self, *args):
        pathlib.Path(sys.argv[3]).write_text('entered')
        time.sleep(30)
p.Model = SlowModel
raise SystemExit(p.main(['--topic','合成測試','--out',sys.argv[2]]))
""")
    child = subprocess.Popen([sys.executable,str(script),str(root),str(out),str(marker)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic()+5
        while not marker.exists() and time.monotonic() < deadline and child.poll() is None:
            time.sleep(0.02)
        assert marker.exists(), "Child did not reach checkpointed model stage"
        child.send_signal(signal.SIGTERM)
        stdout, stderr = child.communicate(timeout=5)
        assert child.returncode == 130, stderr
        report = json.loads(next(out.glob("*/qa_report.json")).read_text())
        assert report["status"] == "CANCELLED" and report["failed_stage"] == "bilingual_topic_expansion"
        assert not list(out.rglob("*.mp4"))
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate()


def test_doctor_reports_policy_and_presence_without_secret(tmp_path, monkeypatch):
    for name in ("LLM_API_KEY", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LLM_API_KEY", "fixture-secret-never-serialize")
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"version":1,"http_network_policy":{"type":"restricted","egress_rules":[{"host":"models.github.ai"}]}}))
    report = diagnose(policy_path=policy)
    assert report["status"] == "PREREQUISITES_BLOCKED"
    assert report["credential_variable_presence"]["LLM_API_KEY"] is True
    assert "fixture-secret" not in json.dumps(report)
    assert "models.github.ai" not in report["domains_denied_by_startup_snapshot"]
    assert "commons.wikimedia.org" in report["domains_denied_by_startup_snapshot"]
    assert all(r["live_operation_tested"] is False for r in report["services"])


def test_absent_policy_cannot_establish_service_readiness(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fixture")
    report = diagnose(policy_path=tmp_path / "absent")
    assert not report["policy_snapshot_available"]
    assert all(r["startup_policy_allows"] is None for r in report["services"])
    assert report["status"] != "READY"


def test_identical_bodies_on_different_sites_are_not_corroboration():
    text = "This is identical syndicated synthetic fixture evidence, not two independent articles."
    sources = [{"id": "S1", "url":"https://one.example.org", "text":text}, {"id":"S2", "url":"https://two.example.net", "text":text}]
    claims = [{"id":f"C{i}", "statement":"合成測試", "date":None,
               "evidence":[{"source_id":"S1","quote":text},{"source_id":"S2","quote":text}]} for i in range(4)]
    with pytest.raises(Blocked) as exc:
        validate_claims(claims, sources)
    assert exc.value.code == "EVIDENCE_INSUFFICIENT"


@pytest.mark.parametrize("date", ["2023-02-29", "1996-13-01", "0000", "2025-04-31"])
def test_impossible_dates_rejected(date):
    quote = "This synthetic quote is long enough for evidence validation and contains no real historical claim."
    sources = [{"id":"S1","url":"https://one.example.org","text":quote+" Source one."}, {"id":"S2","url":"https://two.example.net","text":quote+" Source two."}]
    claims = [{"id":f"C{i}", "statement":"測試", "date":date,
               "evidence":[{"source_id":"S1","quote":quote},{"source_id":"S2","quote":quote}]} for i in range(4)]
    with pytest.raises(Blocked) as exc:
        validate_claims(claims, sources)
    assert exc.value.code == "EVIDENCE_INVALID"


def test_multiscene_real_audio_tone_transitions_follow_caption_timeline(tmp_path):
    # Real encoding/decoding; tones are timing markers, explicitly not AI narration.
    video = tmp_path / "moving.mp4"
    command(["ffmpeg","-v","error","-y","-f","lavfi","-i","testsrc2=s=320x180:r=24:d=3","-c:v","libx264","-threads","2",video])
    sounds = []
    for i, frequency in enumerate((440,880)):
        path = tmp_path / f"tone-{i}.wav"
        command(["ffmpeg","-v","error","-y","-f","lavfi","-i",f"sine=frequency={frequency}:sample_rate=24000:duration=1.113",path])
        sounds.append(path)
    seconds = duration(sounds[0])
    scenes = [{"id":i+1,"narration":"合成測試","info":"音畫同步測試"} for i in range(12)]
    audio = [{"path":str(sounds[i%2]), "seconds":seconds, "cues":[{"start":0.05,"end":seconds-0.05,"text":f"測試{i+1}"}]} for i in range(12)]
    timeline = [[{"path":str(video),"start":0,"end":seconds}] for _ in scenes]
    candidate, cues = render({"scenes":scenes},audio,timeline,tmp_path)
    assert abs(duration(candidate)-12*seconds) < 0.1
    raw = subprocess.check_output(["ffmpeg","-v","error","-i",str(candidate),"-vn","-ar","24000","-ac","1","-f","f32le","-"])
    samples = np.frombuffer(raw, dtype="<f4")
    def dominant_frequency(at):
        window = samples[round((at-0.025)*24000):round((at+0.025)*24000)]
        spectrum = np.abs(np.fft.rfft(window*np.hanning(len(window))))
        return np.fft.rfftfreq(len(window),1/24000)[spectrum.argmax()]
    for i in range(1,12):
        # Check both sides of every expected cut, using decoded audio (not container metadata).
        boundary = cues[i]["start"]-0.05
        assert dominant_frequency(boundary-0.1) == pytest.approx((440,880)[(i-1)%2],abs=30)
        assert dominant_frequency(boundary+0.1) == pytest.approx((440,880)[i%2],abs=30)
    qa = inspect_media(candidate,12*seconds,cues,min_seconds=12,max_seconds=15)
    assert qa["passed"], qa


def test_qa_rejects_audio_ending_before_video(tmp_path):
    path = tmp_path / "short-narration.mp4"
    command(["ffmpeg","-v","error","-y","-f","lavfi","-i","testsrc2=s=1920x1080:r=24:d=4",
             "-f","lavfi","-i","sine=frequency=440:sample_rate=48000:duration=1",
             "-c:v","libx264","-threads","2","-preset","ultrafast","-c:a","aac",path])
    qa = inspect_media(path,4,[{"start":0,"end":4,"text":"合成測試"}],min_seconds=3,max_seconds=5)
    assert not qa["passed"]
    assert "Audio/video stream duration mismatch" in qa["failures"]
    assert "Decoded narration length differs from measured timeline" in qa["failures"]
