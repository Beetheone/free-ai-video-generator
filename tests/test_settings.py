"""Non-secret defaults and safe provider error diagnostics."""
import json

import pytest

from documentary.core import Blocked, Model
from documentary.settings import model_settings


def test_reviewable_config_without_environment_variables(tmp_path, monkeypatch):
    monkeypatch.delenv('LLM_BASE_URL', raising=False)
    monkeypatch.delenv('LLM_MODEL', raising=False)
    path = tmp_path/'model.json'
    path.write_text(json.dumps({'base_url':'https://api.openai.com/v1', 'model':'gpt-4.1-mini'}))
    assert model_settings(path) == ('https://api.openai.com/v1','gpt-4.1-mini')


def test_explicit_user_settings_override_repository(tmp_path, monkeypatch):
    path = tmp_path/'model.json'
    path.write_text(json.dumps({'base_url':'https://api.openai.com/v1', 'model':'gpt-4.1-mini'}))
    monkeypatch.setenv('LLM_BASE_URL','https://provider.example.org/v1')
    monkeypatch.setenv('LLM_MODEL','chosen-vision-model')
    assert model_settings(path) == ('https://provider.example.org/v1','chosen-vision-model')


@pytest.mark.parametrize('data', [
    {'base_url':'https://api.openai.com/v1','model':'test','api_key':'fixture-secret'},
    {'base_url':'https://api.openai.com/v1?api_key=fixture-secret','model':'test'},
    {'base_url':'https://api.openai.com/v1','model':'sk-fixture-secret'},
    {'base_url':42,'model':'test'},
])
def test_provider_config_cannot_embed_credentials(tmp_path, monkeypatch, data):
    monkeypatch.delenv('LLM_BASE_URL', raising=False)
    monkeypatch.delenv('LLM_MODEL', raising=False)
    path = tmp_path/'model.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError) as exc:
        model_settings(path)
    assert 'fixture-secret' not in str(exc.value)


@pytest.mark.parametrize('status,code,param', [(429,'insufficient_quota',None),(400,'unsupported_parameter','max_tokens')])
def test_safe_provider_error_code_without_raw_message(monkeypatch,status,code,param):
    monkeypatch.setenv('LLM_API_KEY','fixture-secret')
    monkeypatch.setenv('LLM_BASE_URL','https://api.openai.com/v1')
    monkeypatch.setenv('LLM_MODEL','test-model')
    class ErrorResponse:
        status_code = status
        def json(self):
            return {'error':{'code':code,'param':param,'message':'fixture-secret should never be echoed'}}
    monkeypatch.setattr('documentary.core.requests.post',lambda *args,**kwargs:ErrorResponse())
    with pytest.raises(Blocked) as exc:
        Model().json('fixture',{})
    assert code in exc.value.detail
    if param: assert param in exc.value.detail
    assert 'fixture-secret' not in exc.value.detail
