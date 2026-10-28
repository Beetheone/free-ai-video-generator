"""Plain-language milestone reports, without publishing retrieved article bodies."""
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from .core import save

STAGES = {
    "bilingual_topic_expansion": "理解題目、產生中英文查詢",
    "research": "搜尋並讀取來源本文",
    "research_repair": "依證據缺口自動補查不同來源（必要時）",
    "evidence_audit": "比對引句、來源與主張",
    "original_script": "撰寫及審核原創繁體中文腳本",
    "licensed_footage_discovery": "尋找授權遊戲影片候選",
    "narration": "製作完整中文旁白與字幕時間",
    "visual_matching": "檢查實際畫面與故事是否相符",
    "render": "剪輯與輸出影片",
    "quality_control": "檢查成品畫面、聲音與字幕",
}


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return default


def write_progress(out, report):
    out = Path(out)
    research = read_json(out / "research.json", {})
    excerpts = read_json(out / "research_excerpts.json", [])
    sources = research.get("sources", []) if isinstance(research, dict) else []
    excerpt_counts = {s["id"]: len(s.get("quotes", [])) or int(bool(s.get("text")))
                      for s in excerpts if isinstance(s, dict) and "id" in s} if isinstance(excerpts, list) else {}
    summary = [{"id": s.get("id"), "hostname": urlsplit(s.get("url", "")).hostname, "title": s.get("title", "")[:120],
                "characters": len(s.get("text", "")), "engine": s.get("discovery_engine", "unknown"),
                "has_relevant_exact_quotes": bool(excerpt_counts.get(s.get("id")))}
               for s in sources if isinstance(s, dict)]
    save(out / "research_summary.json", {"sources": summary, "diagnostics": report.get("diagnostics", {}),
         "search_rounds": research.get("search_rounds", 0),
         "leads_by_engine": dict(Counter(s.get("engine", "unknown") for s in research.get("leads", []) if isinstance(s, dict))),
         "search_errors": [{"engine": e["engine"], "error_type": e.get("error_type")} for e in research.get("errors", []) if "engine" in e],
         "status": report["status"], "failed_stage": report.get("failed_stage"),
         "notice": "Source retrieval and excerpt relevance are not factual verification."})
    lines = ["# 本次製作進度", "", f"題目：{report['topic']}", "",
             "以下為本次實際完成的步驟。自動查核不能保證內容正確，尚未完成的步驟不算成功。", ""]
    done = set(report.get("completed_stages", []))
    for stage, label in STAGES.items():
        state = "已完成" if stage in done else "在此停止" if report.get("failed_stage") == stage else "尚未執行"
        lines.append(f"- {label}：{state}")
    if report.get("blocker"):
        lines += ["", "## 停止原因", "", report["blocker"]["code"], "", report["blocker"]["detail"]]
    lines += ["", "## 已讀取的來源", ""]
    lines.extend(f"- {s.get('id')}：{s.get('title', '')}\n  {s.get('url', '')}" for s in sources if isinstance(s, dict))
    if not sources:
        lines.append("尚無可用來源本文。")
    lines += ["", "## 你現在可以取得什麼", ""]
    if "original_script" in done:
        lines.append("可下載 SCRIPT.md：通過本次自動審核的原創腳本，含逐段主張引用。它尚不是影片。")
    elif "evidence_audit" in done:
        lines.append("可下載 evidence.json：通過本次自動審核的主張、引用與時間線；尚無完整腳本。")
    else:
        lines.append("可下載搜尋、來源與證據缺口紀錄；目前不能把它當作已查證腳本。")
    if report["status"] != "COMPLETE_AUTOMATED_CHECKS":
        lines.append("尚無通過品質檢查的紀錄片 MP4。合法畫面、完整旁白、畫面匹配與成品檢查需各自完成。")
    (out / "PROGRESS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if "original_script" in done:
        script = read_json(out / "script.json", {})
        ledger = read_json(out / "evidence.json", {})
        text = ["# " + script.get("title", report["topic"]), "", "原創繁體中文腳本；引句與模型審核屬自動查核，非人工事實查證。", ""]
        for scene in script.get("scenes", []):
            text += [f"## 段落 {scene['id']}", "", scene["narration"], "", "主張：" + "、".join(scene["claim_ids"]), ""]
        text += ["## 主張與來源", ""]
        for claim in ledger.get("claims", []):
            ids = list(dict.fromkeys(e["source_id"] for e in claim.get("evidence", [])))
            text += [f"- {claim['id']}：{claim['statement']}（{'、'.join(ids)}）"]
        text += ["", "## 來源連結", ""]
        text.extend(f"- {s.get('id')}：{s.get('url', '')}" for s in sources)
        (out / "SCRIPT.md").write_text("\n".join(text) + "\n", encoding="utf-8")
