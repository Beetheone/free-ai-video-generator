"""One history topic in, one finished 10-15 minute MP4 out (research -> hook script -> archive images -> voice -> render).

Every gate that fails writes a report and a nonzero exit code. Nothing is padded, looped or filled with unrelated pictures.
"""
import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from .core import Blocked, Model, Web, save
from .doctor import recovery
from .history import (HISTORY_INSTRUCTION, HISTORY_SECTIONS, ImagePool, assign_images, audit_hook, build_timeline, chip_for,
                      description_text, packaging, pick_music, plan_history)
from .history_render import history_thumbnail, render
from .production import FONT
from .reporting import write_progress

HISTORY_STAGES = {
    "topic_expansion": "理解題目、產生中英文查詢與圖片查詢",
    "research": "搜尋並讀取來源本文",
    "research_repair": "依證據缺口自動補查不同來源（必要時）",
    "evidence_audit": "比對引句、來源與主張",
    "hook_script": "撰寫勾人的原創繁體中文腳本並審核",
    "image_pool": "尋找授權歷史圖片",
    "image_inspection": "逐張檢查圖片實際內容",
    "narration": "製作完整中文旁白與字幕時間",
    "visual_assignment": "把圖片對應到每段旁白",
    "music": "挑選授權背景音樂（沒有也可以）",
    "render": "運鏡、剪輯與輸出影片",
    "quality_control": "檢查成品畫面、聲音與字幕",
    "packaging": "產生標題、縮圖、說明欄與授權清單",
}
CHAPTER_NAMES = ["開場", "背景", "事件升級", "轉折", "真相與爭議", "餘波"]
MIN_SECONDS, MAX_SECONDS = 600, 900


def default_deps():
    """Imported lazily: the research stack (OpenCC, trafilatura, ...) is only needed for real runs."""
    from . import production, research
    return SimpleNamespace(research=research.research, fact_check=research.fact_check, plan_repair=research.plan_repair,
                           write_script=research.write_script, synthesize=production.synthesize, inspect_media=production.inspect_media)


def _diagnostics(out):
    counts = {}
    for filename, field, label in (("research.json", "sources", "retrieved_source_bodies"),
                                   ("evidence_draft.json", "claims", "candidate_claims"),
                                   ("evidence.json", "claims", "audited_and_retained_claims"),
                                   ("image_sources.json", "records", "licensed_images_downloaded")):
        try:
            data = json.loads((out / filename).read_text("utf-8"))
            value = data.get(field) if isinstance(data, dict) else None
            counts[label] = len(value) if isinstance(value, list) else None
        except (OSError, ValueError):
            continue
    try:
        tags = json.loads((out / "image_tags.json").read_text("utf-8"))
        counts["images_inspected"] = len(tags)
        counts["images_usable"] = sum(1 for t in tags.values() if t.get("usable"))
    except (OSError, ValueError, AttributeError):
        pass
    return counts


def run_history(topic, minutes, out, engine="edge", voice="zh-TW-YunJheNeural", *, model=None, web=None, stop_after="movie",
                bounds=(MIN_SECONDS, MAX_SECONDS), deps=None, pool_delay=0.25):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    stage = "preflight"
    report = {"topic": topic, "mode": "history", "target_minutes": minutes, "tts_engine": engine, "requested_output": stop_after,
              "run_id": out.name, "started_at": datetime.now(timezone.utc).isoformat(), "status": "RUNNING",
              "current_stage": stage, "completed_stages": []}
    save(out / "qa_report.json", report)

    def enter(name):
        nonlocal stage
        stage = name
        report.update(current_stage=name, updated_at=datetime.now(timezone.utc).isoformat())
        report.pop("progress", None)
        save(out / "qa_report.json", report)
        if os.getenv("GITHUB_ACTIONS") == "true":
            print(f"::notice title=History stage::{name}", flush=True)

    def complete():
        report["completed_stages"].append(stage)
        report.update(updated_at=datetime.now(timezone.utc).isoformat())
        save(out / "qa_report.json", report)

    def progress(done, total):
        report.update(progress={"completed": done, "total": total}, updated_at=datetime.now(timezone.utc).isoformat())
        save(out / "qa_report.json", report)

    try:
        deps = deps or default_deps()
        model, web = model or Model(), web or Web()
        if not topic.strip() or len(topic) > 500 or not isinstance(minutes, int) or not 10 <= minutes <= 15 or stop_after not in ("research", "script", "movie"):
            raise Blocked("INPUT_INVALID", "Topic must be 1–500 characters and runtime 10–15 minutes")
        if stop_after == "movie" and (not all(shutil.which(p) for p in ("ffmpeg", "ffprobe")) or not Path(FONT).is_file()):
            raise Blocked("RUNTIME_MISSING", "Need ffmpeg, ffprobe and fonts-noto-cjk")

        enter("topic_expansion")
        plan = plan_history(model, topic)
        save(out / "topic.json", plan)
        complete()

        enter("research")
        sources = deps.research(web, plan, out)
        complete()

        enter("evidence_audit")
        quote_cache = {}
        for attempt in range(2):
            try:
                ledger = deps.fact_check(model, plan, sources, out, quote_cache=quote_cache)
                break
            except Blocked as exc:
                save(out / f"evidence_attempt_{attempt+1}.json", {"code": exc.code, "detail": exc.detail})
                if exc.code != "EVIDENCE_INSUFFICIENT" or attempt == 1 or len(sources) < 3:
                    raise
                enter("research_repair")
                sources = deps.research(web, deps.plan_repair(model, plan, sources, out), out, previous=sources)
                complete()
                enter("evidence_audit")
        complete()
        if stop_after == "research":
            report["status"] = "RESEARCH_READY"
            return report

        enter("hook_script")
        script = deps.write_script(model, plan, ledger, minutes, out, sections=HISTORY_SECTIONS, instruction=HISTORY_INSTRUCTION)
        claims_by_id = {c["id"]: c for c in ledger["claims"]}
        for scene in script["scenes"]:
            scene["chip"] = chip_for(scene, claims_by_id)
        try:
            hook = audit_hook(model, script["scenes"], ledger)
        except Blocked as exc:
            # The hook check is advisory; never discard a finished, evidence-audited script because of it.
            hook = {"passed": None, "error": exc.code}
        save(out / "hook_audit.json", hook)
        report["hook_audit"] = {"passed": hook["passed"]}
        save(out / "script.json", script)
        complete()
        if stop_after == "script":
            report["status"] = "SCRIPT_READY"
            return report

        enter("image_pool")
        pool = ImagePool(web, model, out, delay=pool_delay)
        pool.seed_from_articles(plan["reference_titles_en"])
        pool.search(plan["image_queries"])
        for scene in script["scenes"]:
            pool.search(scene["footage_queries"])
        if len(pool.records) < 8:
            raise Blocked("VISUALS_INSUFFICIENT", f"Only {len(pool.records)} licensed images were found for this topic; inspect image_sources.json. No unrelated stand-ins are used.")
        complete()

        enter("image_inspection")
        pool.tag(plan)
        complete()

        enter("narration")
        narration = []
        (out / "audio").mkdir()
        for scene in script["scenes"]:
            ext = ".mp3" if engine == "edge" else ".wav"
            target = out / "audio" / (str(scene["id"]) + ext)
            try:
                item = deps.synthesize(scene["narration"], target, engine, voice)
            except Blocked as exc:
                # Edge is free but depends on a Microsoft endpoint; fall back to local Kokoro when it is installed.
                if exc.code != "TTS_UNAVAILABLE" or engine != "edge" or narration:
                    raise
                engine = "kokoro"
                report["tts_engine"] = "kokoro (fallback: edge unavailable)"
                target = out / "audio" / (str(scene["id"]) + ".wav")
                item = deps.synthesize(scene["narration"], target, engine, voice)
            narration.append(item)
            save(out / "narration.json", narration)
            progress(len(narration), len(script["scenes"]))
        seconds = sum(a["seconds"] for a in narration)
        if bounds and not bounds[0] <= seconds <= bounds[1]:
            raise Blocked("NARRATION_RUNTIME", f"Measured {seconds:.1f}s outside the {bounds[0]//60}–{bounds[1]//60} minute range; no slowing, looping or filler")
        complete()

        enter("visual_assignment")
        chosen = assign_images(model, plan, script["scenes"], pool, out)
        timeline = build_timeline(script["scenes"], [a["seconds"] for a in narration], chosen, pool)
        save(out / "edit_decisions.json", timeline)
        complete()

        enter("music")
        music = pick_music(web, out, delay=pool_delay)
        report["music"] = bool(music)
        complete()

        enter("render")
        candidate, cues = render(script, narration, timeline, [s["chip"] for s in script["scenes"]], out, music["path"] if music else None)
        complete()

        enter("quality_control")
        technical = deps.inspect_media(candidate, seconds, cues, *(bounds or (1, 10_000)))
        save(out / "media_qa.json", technical)
        if not technical["passed"]:
            raise Blocked("RENDER_QA_FAILED", "; ".join(technical["failures"]))
        complete()

        enter("packaging")
        used = {s["asset_id"] for shots in timeline for s in shots}
        images = [r for r in pool.records if r["id"] in used]
        pack = packaging(model, plan, ledger, script)
        starts, offset, seen = [], 0.0, set()
        for scene, audio in zip(script["scenes"], narration):
            chapter = scene.get("chapter", 0)
            if chapter not in seen:
                seen.add(chapter)
                starts.append((offset, CHAPTER_NAMES[chapter] if chapter < len(CHAPTER_NAMES) else f"第{chapter+1}章"))
            offset += audio["seconds"]
        if starts and starts[0][0] != 0:
            starts[0] = (0.0, starts[0][1])
        cited = {e["source_id"] for c in ledger["claims"] for e in c.get("evidence", [])}
        cited_sources = [s for s in sources if s.get("id") in cited]
        description = description_text(pack, starts, cited_sources, images, music)
        best = max(images, key=lambda r: (r["tags"]["impact"], r["tags"]["relevance"]))
        history_thumbnail(best["path"], pack["thumbnail_text"], out / "thumbnail.jpg")
        (out / "DESCRIPTION.txt").write_text(description, encoding="utf-8")
        save(out / "packaging.json", {**pack, "tags": pack["tags"], "chapters": [{"start": s, "name": n} for s, n in starts], "thumbnail_asset": best["id"]})
        credits = ["# 素材來源與授權", ""]
        credits += [f"- {r['title']} — {r['creator']}\n  {r['source_url']}\n  {r['license']} {r['license_url']}".rstrip() for r in images]
        if music:
            credits += ["", f"音樂：{music['title']} — {music['creator']}\n  {music['source_url']}\n  {music['license']}"]
        credits += ["", "授權依 Wikimedia Commons 檔案頁中繼資料判斷，非獨立法律保證。圖片經 Ken Burns 縮放、裁切與字幕疊加。"]
        (out / "ATTRIBUTION.md").write_text("\n".join(credits) + "\n", encoding="utf-8")
        save(out / "sources.json", {"topic": topic, "research": [{k: v for k, v in s.items() if k != "text"} for s in sources],
             "evidence": ledger, "images": [{k: v for k, v in r.items() if k not in ("path", "preview")} for r in images],
             "music": {k: v for k, v in (music or {}).items() if k != "path"} or None,
             "model": getattr(model, "name", "test_provider"), "voice": voice if engine == "edge" else "Kokoro Mandarin (not Taiwanese accent)",
             "publication_notice": "Review before publishing. Enable the altered/synthetic content disclosure when uploading."})
        candidate.replace(out / "documentary.mp4")
        complete()
        report.update(status="COMPLETE_AUTOMATED_CHECKS", seconds=seconds, title=pack["title"],
                      notice="Automated source and visual checks cannot guarantee factual or legal correctness; review before publishing.")
    except Blocked as exc:
        report.update(status="BLOCKED", failed_stage=stage, blocker={"code": exc.code, "detail": exc.detail})
    except subprocess.TimeoutExpired:
        report.update(status="BLOCKED", failed_stage=stage, blocker={"code": "MEDIA_TIMEOUT", "detail": "Media step exceeded its time budget; no finished output is released"})
    except (KeyboardInterrupt, InterruptedError):
        report.update(status="CANCELLED", failed_stage=stage, blocker={"code": "RUN_INTERRUPTED", "detail": "Production interrupted; partial artifacts are not a finished video"})
    except Exception as exc:
        report.update(status="ERROR", failed_stage=stage, blocker={"code": "UNEXPECTED_ERROR", "detail": type(exc).__name__})
    finally:
        if report.get("blocker"):
            report["next_actions"] = recovery(report["blocker"]["code"])
        counts = _diagnostics(out)
        if counts:
            report["diagnostics"] = counts
        report.update(finished_at=datetime.now(timezone.utc).isoformat(), model_calls=getattr(model, "calls", 0),
                      model_usage=getattr(model, "usage", {}), model_usage_unavailable_calls=getattr(model, "usage_unavailable_calls", 0))
        save(out / "qa_report.json", report)
        write_progress(out, report, HISTORY_STAGES)
    return report


def _main(argv=None):
    p = argparse.ArgumentParser(description="歷史題目 → 可查核研究 → 勾人腳本 → 授權歷史圖片 → 10–15 分鐘 MP4")
    inputs = p.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--topic")
    inputs.add_argument("--topics-file", type=Path, help="JSON array of 1–3 topic strings")
    p.add_argument("--minutes", type=int, choices=range(10, 16), default=12)
    p.add_argument("--out", type=Path, default=Path("output/history"))
    p.add_argument("--tts", choices=("edge", "kokoro"), default="edge")
    p.add_argument("--voice", default="zh-TW-YunJheNeural")
    p.add_argument("--stop-after", choices=("research", "script", "movie"), default="movie")
    args = p.parse_args(argv)
    topics = [args.topic] if args.topic is not None else json.loads(args.topics_file.read_text("utf-8"))
    if not isinstance(topics, list) or not 1 <= len(topics) <= 3 or any(not isinstance(t, str) or not t.strip() or len(t) > 500 for t in topics):
        p.error("Provide 1–3 nonempty topic strings, each <=500 characters")
    args.out.mkdir(parents=True, exist_ok=True)
    reports = []
    for topic in topics:
        slug = re.sub(r"[^\w-]", "_", topic)[:30]
        name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + slug + "-" + uuid.uuid4().hex[:8]
        report = run_history(topic, args.minutes, args.out / name, args.tts, args.voice, stop_after=args.stop_after)
        reports.append(report)
        print(json.dumps(report, ensure_ascii=False), flush=True)
        if report["status"] == "CANCELLED":
            return 130
    expected = {"research": "RESEARCH_READY", "script": "SCRIPT_READY", "movie": "COMPLETE_AUTOMATED_CHECKS"}[args.stop_after]
    return 0 if all(r["status"] == expected for r in reports) else 2


def main(argv=None):
    previous = signal.getsignal(signal.SIGTERM)

    def interrupted(signum, frame):
        raise InterruptedError("Production terminated")
    signal.signal(signal.SIGTERM, interrupted)
    try:
        return _main(argv)
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    sys.exit(main())
