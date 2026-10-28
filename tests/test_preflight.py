"""Explicit fake API responses test the smoke checker, not external readiness."""
import base64
import io
import json

from PIL import Image
import pytest

from documentary import preflight
from documentary.core import Blocked


@pytest.mark.parametrize("base,name", [
    ("https://api.openai.com/v1", "gpt-4.1-mini"),
    (preflight.GEMINI_BASE, "gpt-4.1-mini"),
    ("https://generativelanguage.googleapis.com/v1beta", "gemini-flash-latest"),
])
def test_old_provider_override_never_receives_gemini_key(tmp_path, monkeypatch, base, name):
    monkeypatch.setenv("LLM_API_KEY", "fixture-secret")
    monkeypatch.setenv("LLM_BASE_URL", base)
    monkeypatch.setenv("LLM_MODEL", name)
    def forbidden(*a, **k):
        raise AssertionError("No request may send this key to the old endpoint")
    monkeypatch.setattr("documentary.core.requests.post", forbidden)
    with pytest.raises(Blocked) as exc:
        preflight.check_model(tmp_path)
    assert exc.value.code == "MODEL_PROVIDER_MISMATCH"
    assert "fixture-secret" not in exc.value.detail


@pytest.mark.parametrize("correct", [True, False])
def test_model_checker_sends_real_image_and_validates_known_content(tmp_path, monkeypatch, correct):
    monkeypatch.setenv("LLM_API_KEY", "fixture-secret")
    monkeypatch.setenv("LLM_BASE_URL", preflight.GEMINI_BASE)
    monkeypatch.setenv("LLM_MODEL", "gemini-flash-latest")
    class Response:
        status_code = 200
        def json(self):
            result = {"left_color": "red" if correct else "fixture-secret", "right_color": "blue", "echo": "繁體中文環境確認"}
            return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(result)}}]}
    def post(url, **kw):
        assert url == preflight.GEMINI_BASE + "/chat/completions"
        assert kw["headers"]["Authorization"] == "Bearer fixture-secret"
        content = kw["json"]["messages"][1]["content"]
        data = base64.b64decode(content[1]["image_url"]["url"].split(",")[1])
        image = Image.open(io.BytesIO(data))
        assert image.getpixel((20, 40))[0] > 240
        assert image.getpixel((120, 40))[2] > 240
        return Response()
    monkeypatch.setattr("documentary.core.requests.post", post)
    if correct:
        report = preflight.check_model(tmp_path)
        assert report["inference_calls"] == 1
        assert "fixture-secret" not in json.dumps(report)
    else:
        with pytest.raises(Blocked) as exc:
            preflight.check_model(tmp_path)
        assert exc.value.code == "MODEL_SMOKE_FAILED"
        assert "fixture-secret" not in exc.value.detail


def test_independent_services_still_report_after_model_blocker(tmp_path, monkeypatch):
    def blocked(_):
        raise Blocked("MODEL_PROVIDER_MISMATCH", "Old provider override")
    monkeypatch.setattr(preflight, "check_model", blocked)
    for name in ("check_search", "check_commons", "check_voice"):
        monkeypatch.setattr(preflight, name, lambda *a, **k: {"scope": "explicit fake test"})
    out = tmp_path / "new-run"
    report = preflight.verify(out)
    assert report["status"] == "BLOCKED"
    assert report["checks"]["taiwan_voice"]["status"] == "PASS"
    assert json.loads((out / "report.json").read_text())["status"] == "BLOCKED"
    with pytest.raises(FileExistsError):
        preflight.verify(out)


def test_voice_only_does_not_spend_model_quota_or_claim_all_services_pass(tmp_path, monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("Voice-only check must not call model, search or footage services")
    for name in ("check_model", "check_search", "check_commons"):
        monkeypatch.setattr(preflight, name, forbidden)
    def voice(out, engine):
        assert engine == "kokoro"
        return {"scope": "explicit fake test"}
    monkeypatch.setattr(preflight, "check_voice", voice)
    report = preflight.verify(tmp_path / "voice-run", voice_only=True, engine="kokoro")
    assert report["status"] == "SELECTED_SERVICE_CHECKS_PASS"
    assert set(report["checks"]) == {"mandarin_voice"}
