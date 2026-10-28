"""Milestones use explicit synthetic fixtures, never claimed real stories."""
import json

import pytest

from documentary import pipeline
from documentary.core import Blocked, save


@pytest.mark.parametrize("milestone,expected", [("research", "RESEARCH_READY"), ("script", "SCRIPT_READY")])
def test_milestone_never_runs_production_or_claims_finished_film(tmp_path, monkeypatch, milestone, expected):
    def forbidden(*a, **k):
        pytest.fail("Explicit research/script output must not run film production")
    monkeypatch.setattr(pipeline.shutil, "which", lambda _: None)
    monkeypatch.setattr(pipeline, "Library", forbidden)
    monkeypatch.setattr(pipeline, "synthesize", forbidden)
    monkeypatch.setattr(pipeline, "plan_topic", lambda *a: {})
    def research(web, plan, out):
        sources = [{"id": "S1", "title": "Fixture", "url": "https://fixture.example.org/article", "text": "raw-source-must-not-appear-in-readable-report"}]
        save(out / "research.json", {"sources": sources})
        return sources
    def fact_check(model, plan, sources, out):
        ledger = {"claims": [{"id": "C1", "statement": "僅合成測試", "evidence": [{"source_id": "S1"}]}]}
        save(out / "evidence.json", ledger)
        return ledger
    monkeypatch.setattr(pipeline, "research", research)
    monkeypatch.setattr(pipeline, "fact_check", fact_check)
    def script(model, plan, ledger, minutes, out):
        data = {"title": "合成測試", "scenes": [{"id": 1, "narration": "這是明示合成的腳本測試。", "claim_ids": ["C1"]}]}
        save(out / "script.json", data)
        return data
    monkeypatch.setattr(pipeline, "write_script", script if milestone == "script" else forbidden)
    out = tmp_path / "milestone"
    report = pipeline.run_pipeline("合成測試", 12, out, model=object(), web=object(), stop_after=milestone)
    assert report["status"] == expected
    assert report["status"] != "COMPLETE_AUTOMATED_CHECKS"
    assert json.loads((out / "qa_report.json").read_text())["status"] == expected
    progress = (out / "PROGRESS.md").read_text()
    assert "尚無通過品質檢查的紀錄片 MP4" in progress
    assert "raw-source-must-not-appear" not in progress
    assert (out / "SCRIPT.md").is_file() == (milestone == "script")
    assert not list(out.rglob("*.mp4"))


def test_failed_evidence_produces_plain_report_without_script(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "plan_topic", lambda *a: {})
    monkeypatch.setattr(pipeline, "research", lambda *a: [])
    def blocked(*a):
        raise Blocked("EVIDENCE_INSUFFICIENT", "Explicit fixture with insufficient corroboration")
    monkeypatch.setattr(pipeline, "fact_check", blocked)
    out = tmp_path / "blocked"
    report = pipeline.run_pipeline("合成測試", 12, out, model=object(), web=object(), stop_after="script")
    assert report["status"] == "BLOCKED"
    assert "在此停止" in (out / "PROGRESS.md").read_text()
    assert not (out / "SCRIPT.md").exists()
