"""Provider envelope fixtures are synthetic, not evidence of a live model result."""
import json

import pytest

from documentary.core import Blocked, Model


def fake_response(monkeypatch, body):
    monkeypatch.setenv("LLM_API_KEY", "fixture-secret")
    monkeypatch.setenv("LLM_BASE_URL", "https://provider.example.org/v1")
    monkeypatch.setenv("LLM_MODEL", "fixture")
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


def test_non_json_response_exposes_only_protocol_metadata(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "fixture-secret")
    monkeypatch.setenv("LLM_BASE_URL", "https://provider.example.org/v1")
    monkeypatch.setenv("LLM_MODEL", "fixture")
    class HtmlResponse:
        status_code = 200
        content = b"<!doctype html><html>fixture-secret in a provider error</html>"
        headers = {"Content-Type":"text/html; charset=utf-8"}
        def json(self): raise ValueError
    def post(url, **kw):
        assert url.endswith('/chat/completions')
        assert kw['headers']['Accept'] == 'application/json'
        assert kw['json']['stream'] is False
        assert kw['allow_redirects'] is False
        return HtmlResponse()
    monkeypatch.setattr("documentary.core.requests.post", post)
    with pytest.raises(Blocked) as exc:
        Model().json("fixture", {})
    assert exc.value.code == "MODEL_PROTOCOL"
    assert "body_kind=html" in exc.value.detail
    assert "media_type=text/html" in exc.value.detail
    assert "fixture-secret" not in exc.value.detail


def test_github_token_is_not_reused_as_another_provider_key(monkeypatch):
    monkeypatch.delenv('LLM_API_KEY', raising=False)
    monkeypatch.setenv('GH_TOKEN', 'fixture-github-token')
    monkeypatch.setenv('GITHUB_TOKEN', 'fixture-github-token')
    with pytest.raises(Blocked) as exc:
        Model().json('fixture', {})
    assert exc.value.code == 'MODEL_CREDENTIAL_REQUIRED'


@pytest.mark.parametrize('host', ['models.github.ai/inference', 'models.inference.ai.azure.com'])
def test_retired_github_models_fails_without_requesting_more_tokens(monkeypatch, host):
    monkeypatch.setenv('LLM_BASE_URL', 'https://'+host)
    monkeypatch.setenv('LLM_API_KEY', 'fixture')
    def forbidden(*args, **kwargs):
        pytest.fail('A retired service must not receive another inference request')
    monkeypatch.setattr('documentary.core.requests.post', forbidden)
    with pytest.raises(Blocked) as exc:
        Model().json('fixture', {})
    assert exc.value.code == 'MODEL_PROVIDER_RETIRED'
    assert '2026-07-30' in exc.value.detail


def test_generic_key_is_never_sent_to_an_implicit_provider(monkeypatch):
    monkeypatch.setenv('LLM_API_KEY', 'fixture')
    monkeypatch.delenv('LLM_BASE_URL', raising=False)
    monkeypatch.delenv('LLM_MODEL', raising=False)
    def forbidden(*args, **kwargs):
        pytest.fail('No provider was selected; do not transmit the key')
    monkeypatch.setattr('documentary.core.requests.post', forbidden)
    with pytest.raises(Blocked) as exc:
        Model().json('fixture', {})
    assert exc.value.code == 'MODEL_CONFIG'
