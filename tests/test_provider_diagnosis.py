"""Provider error fixtures and read-only catalog checks never generate text."""
import json

from documentary.core import provider_error
from documentary.probe import main, probe_catalog


def test_quota_reason_in_type_or_message_does_not_leak_raw_text():
    class Response:
        headers = {'Content-Type':'application/json','Retry-After':'60'}
        def json(self):
            return {'error':{'type':'insufficient_quota','message':'fixture-secret'}}
    meta = provider_error(Response())
    assert meta['code']=='insufficient_quota'
    assert meta['retry_after_seconds']==60
    assert 'fixture-secret' not in json.dumps(meta)
    class MessageOnly(Response):
        def json(self):
            return {'error':{'message':'fixture-secret: You exceeded your current quota, please check your plan and billing details.'}}
    assert provider_error(MessageOnly())['code']=='insufficient_quota'


def test_html_error_cannot_be_interpreted_as_billing_evidence():
    class Html:
        headers = {'Content-Type':'text/html; charset=utf-8'}
        text = 'fixture-secret: exceeded your current quota'
        def json(self): raise ValueError
    meta = provider_error(Html())
    assert meta=={'media_type':'text/html'}


def test_catalog_diagnosis_is_read_only_and_not_inference_readiness(monkeypatch):
    monkeypatch.setenv('LLM_API_KEY','fixture-secret')
    monkeypatch.setenv('LLM_BASE_URL','https://api.openai.com/v1')
    monkeypatch.setenv('LLM_MODEL','gpt-4.1-mini')
    class Response:
        status_code = 200
        headers = {'Content-Type':'application/json'}
        def json(self): return {'data':[{'id':'gpt-4.1-mini'}]}
    def get(url,**kw):
        assert url=='https://api.openai.com/v1/models'
        assert kw['headers']['Authorization']=='Bearer fixture-secret'
        assert kw['allow_redirects'] is False
        return Response()
    monkeypatch.setattr('documentary.probe.requests.get',get)
    monkeypatch.setattr('documentary.core.requests.post',lambda *a,**k: (_ for _ in ()).throw(AssertionError('Inference must not run')))
    report = probe_catalog()
    assert report['status']=='CATALOG_ACCESSIBLE_INFERENCE_UNVERIFIED'
    assert report['chosen_model_listed'] is True
    assert report['inference_tested'] is False
    assert 'fixture-secret' not in json.dumps(report)


def test_known_quota_failure_does_not_trigger_more_requests(tmp_path,monkeypatch):
    run = tmp_path/'runs'/'one';run.mkdir(parents=True)
    (run/'qa_report.json').write_text(json.dumps({'blocker':{'code':'MODEL_UNAVAILABLE','detail':'HTTP 429; code=insufficient_quota'}}))
    def forbidden(): raise AssertionError('No request is needed after an explicit quota error')
    monkeypatch.setattr('documentary.probe.probe_catalog',forbidden)
    out = tmp_path/'diagnosis.json'
    assert main(['--after-failed-run',str(tmp_path/'runs'),'--out',str(out)])==0
    assert json.loads(out.read_text())['status']=='NOT_NEEDED'
