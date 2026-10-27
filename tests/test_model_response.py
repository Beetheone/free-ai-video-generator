"""Provider envelope fixtures are synthetic, not evidence of a live model result."""
import json

import pytest

from documentary.core import Blocked, Model


def fake_response(monkeypatch, body):
    monkeypatch.setenv("LLM_API_KEY", "fixture-secret")
    monkeypatch.setenv("LLM_MIN_INTERVAL", "0")
    class Response:
        status_code = 200
        def json(self): return body
    monkeypatch.setattr("documentary.core.requests.post", lambda *a, **kw: Response())


@pytest.mark.parametrize("usage", [None, {}, {"prompt_tokens":None,"completion_tokens":None}])
def test_unavailable_usage_does_not_reject_valid_completion(monkeypatch, usage):
    fake_response(monkeypatch, {"usage":usage,"choices":[{"finish_reason":"stop","message":{"content":'{"test":true}'}}]})
    model = Model()
    assert model.json("fixture", {}) == {"test":True}
    assert model.usage_unavailable_calls == 1


def test_normal_accounting_and_whole_json_fence(monkeypatch):
    fake_response(monkeypatch, {"usage":{"prompt_tokens":12,"completion_tokens":4},"choices":[{"finish_reason":"stop","message":{"content":'```json\n{"test":true}\n```'}}]})
    model = Model()
    assert model.json("fixture", {}) == {"test":True}
    assert model.usage == {"prompt_tokens":12,"completion_tokens":4}
    assert model.usage_unavailable_calls == 0


@pytest.mark.parametrize("body", [{}, {"choices":[]}, {"choices":[None]}, {"choices":[{"finish_reason":"stop","message":{"content":None}}]}])
def test_incompatible_envelope_has_safe_specific_diagnostic(monkeypatch, body):
    fake_response(monkeypatch, body)
    with pytest.raises(Blocked) as exc:
        Model().json("fixture", {})
    assert exc.value.code == "MODEL_SCHEMA"
    assert "withheld" in exc.value.detail


def test_arbitrary_prose_does_not_get_json_extracted(monkeypatch):
    # Only a whole JSON fence is supported; do not fish a valid-looking object
    # from contradictory prose and silently treat it as a vetted response.
    fake_response(monkeypatch, {"choices":[{"finish_reason":"stop","message":{"content":'fixture-secret {"test":true}'}}]})
    with pytest.raises(Blocked) as exc:
        Model().json("fixture", {})
    assert "line 1, column 1" in exc.value.detail
    assert "fixture-secret" not in exc.value.detail
