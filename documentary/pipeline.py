"""Topic-only controller. A failed gate always has a report and nonzero exit code."""
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

from .core import Blocked, Model, Web, save
from .doctor import recovery
from .footage import Library
from .production import FONT, inspect_media, render, synthesize, thumbnail
from .research import fact_check, plan_repair, plan_topic, research, write_script
from .reporting import write_progress


def run_pipeline(topic, minutes, out, engine="edge", voice="zh-TW-YunJheNeural", *, model=None, web=None, stop_after="movie"):
    out = Path(out)
    # Never accept a stale successful MP4/report from a previous job as this job's output.
    out.mkdir(parents=True, exist_ok=False)
    stage = "preflight"
    report = {"topic": topic, "target_minutes": minutes, "tts_engine": engine, "requested_output": stop_after, "run_id": out.name,
              "started_at": datetime.now(timezone.utc).isoformat(), "status": "RUNNING", "current_stage": stage, "completed_stages": []}
    save(out / "qa_report.json", report)

    def enter(name):
        nonlocal stage
        stage = name
        report.update(current_stage=name, updated_at=datetime.now(timezone.utc).isoformat())
        report.pop("progress", None)
        save(out / "qa_report.json", report)
        if os.getenv("GITHUB_ACTIONS") == "true":
            # Stage names are fixed application identifiers, never topic/source
            # text. Public annotations expose progress without secret logs.
            print(f"::notice title=Documentary stage::{name}", flush=True)

    def complete():
        report["completed_stages"].append(stage)
        report.update(updated_at=datetime.now(timezone.utc).isoformat())
        save(out / "qa_report.json", report)

    def progress(done, total):
        report.update(progress={"completed": done, "total": total}, updated_at=datetime.now(timezone.utc).isoformat())
        save(out / "qa_report.json", report)

    try:
        model, web = model or Model(), web or Web()
        if not topic.strip() or len(topic) > 500 or minutes not in (10,12,15) or stop_after not in ("research", "script", "movie"):
            raise Blocked("INPUT_INVALID", "Topic must be 1–500 characters and runtime 10, 12 or 15 minutes")
        if stop_after == "movie" and (not all(shutil.which(p) for p in ("ffmpeg", "ffprobe")) or not Path(FONT).is_file()):
            raise Blocked("RUNTIME_MISSING", "Need ffmpeg, ffprobe and fonts-noto-cjk")
        enter("bilingual_topic_expansion")
        plan = plan_topic(model, topic)
        save(out / "topic.json", plan)
        complete()
        enter("research")
        sources = research(web, plan, out)
        complete()
        enter("evidence_audit")
        quote_cache = {}
        for attempt in range(2):
            try:
                ledger = fact_check(model, plan, sources, out, quote_cache=quote_cache)
                break
            except Blocked as exc:
                save(out / f"evidence_attempt_{attempt+1}.json", {"code": exc.code, "detail": exc.detail})
                if exc.code != "EVIDENCE_INSUFFICIENT" or attempt == 1 or len(sources) < 3:
                    raise
                enter("research_repair")
                repaired_plan = plan_repair(model, plan, sources, out)
                sources = research(web, repaired_plan, out, previous=sources)
                complete()
                enter("evidence_audit")
        complete()
        if stop_after == "research":
            report["status"] = "RESEARCH_READY"
            return report
        enter("original_script")
        script = write_script(model, plan, ledger, minutes, out)
        complete()
        if stop_after == "script":
            report["status"] = "SCRIPT_READY"
            return report
        enter("licensed_footage_discovery")
        library = Library(web, model, out)
        library.search(plan["footage_queries"])
        if not library.records:
            raise Blocked("LICENSED_GAMEPLAY_MISSING", "No supported licensed candidate videos found; inspect media_sources.json. No stock or text-card substitute.")
        complete()
        enter("narration")
        narration = []
        (out / "audio").mkdir()
        for scene in script["scenes"]:
            ext = ".mp3" if engine == "edge" else ".wav"
            narration.append(synthesize(scene["narration"], out / "audio" / (str(scene["id"])+ext), engine, voice))
            save(out / "narration.json", narration)
            progress(len(narration), len(script["scenes"]))
        seconds = sum(a["seconds"] for a in narration)
        if not 600 <= seconds <= 900 or not minutes*60*0.85 <= seconds <= minutes*60*1.15:
            raise Blocked("NARRATION_RUNTIME", f"Measured {seconds:.1f}s not within requested 10–15 minute range/tolerance; no slowing, looping or filler")
        complete()
        enter("visual_matching")
        timeline = []
        for scene, audio in zip(script["scenes"], narration, strict=True):
            timeline.append(library.match(scene, audio["seconds"]))
            save(out / "edit_decisions.json", timeline)
            progress(len(timeline), len(script["scenes"]))
        complete()
        used = {s["asset_id"] for shots in timeline for s in shots}
        credits = [r for r in library.records if r["id"] in used]
        credits_text = "# 素材來源與使用說明\n\n"
        for r in credits:
            credits_text += f"- {r['title']} — {r['creator']}\n  {r['source_url']}\n  {r['license']} {r['license_url']}\n  改作：裁切、縮放、靜音、剪輯、旁白、字幕及封面擷取。\n"
        credits_text += "\n來源授權依檔案頁中繼資料判斷；非獨立法律保證。研究內容經自動引句與模型審核，非人工查證。\n"
        (out / "ATTRIBUTION.md").write_text(credits_text, encoding="utf-8")
        save(out / "sources.json", {"topic": topic, "research": [{k:v for k,v in s.items() if k != "text"} for s in sources],
             "evidence": ledger, "media": credits, "edit_decisions": timeline, "thumbnail_asset": timeline[0][0]["asset_id"],
             "model": getattr(model, "name", "test_provider"), "voice": voice if engine == "edge" else "Kokoro Mandarin (not Taiwanese accent)",
             "publication_notice": "Include ATTRIBUTION.md credits in your YouTube description. No automatic upload/publication."})
        enter("render")
        candidate, cues = render(script, narration, timeline, out)
        complete()
        enter("quality_control")
        technical = inspect_media(candidate, seconds, cues)
        save(out / "media_qa.json", technical)
        if not technical["passed"]:
            raise Blocked("RENDER_QA_FAILED", "; ".join(technical["failures"]))
        thumbnail(candidate, topic, out / "thumbnail.jpg")
        candidate.replace(out / "documentary.mp4")
        complete()
        report.update(status="COMPLETE_AUTOMATED_CHECKS", seconds=seconds,
                      notice="Automated source/visual checks cannot guarantee factual or legal correctness; editorial review is still recommended.")
    except Blocked as exc:
        report.update(status="BLOCKED", failed_stage=stage, blocker={"code": exc.code, "detail": exc.detail})
    except subprocess.TimeoutExpired:
        report.update(status="BLOCKED", failed_stage=stage, blocker={"code": "MEDIA_TIMEOUT", "detail": "Media inspection exceeded its time budget; no finished output is released"})
    except (KeyboardInterrupt, InterruptedError):
        report.update(status="CANCELLED", failed_stage=stage, blocker={"code": "RUN_INTERRUPTED", "detail": "Production interrupted; partial artifacts are not a finished film"})
    except Exception as exc:
        report.update(status="ERROR", failed_stage=stage, blocker={"code": "UNEXPECTED_ERROR", "detail": type(exc).__name__})
    finally:
        if report.get("blocker"):
            report["next_actions"] = recovery(report["blocker"]["code"])
        # Only counts are included in public diagnostics; source bodies, model
        # prose and provider responses remain in their own artifacts.
        counts = {}
        for filename, field, label in (("research.json", "sources", "retrieved_source_bodies"),
                                        ("research_excerpts.json", None, "sources_with_relevant_exact_quotes"),
                                        ("evidence_draft.json", "claims", "candidate_claims")):
            try:
                data = json.loads((out / filename).read_text("utf-8"))
                value = data.get(field) if field and isinstance(data, dict) else data if field is None else None
                counts[label] = len(value) if isinstance(value, list) else None
            except (OSError, ValueError):
                continue
        if counts:
            report["diagnostics"] = counts
        report.update(finished_at=datetime.now(timezone.utc).isoformat(),
                      model_calls=getattr(model, "calls", 0), model_usage=getattr(model, "usage", {}),
                      model_usage_unavailable_calls=getattr(model, "usage_unavailable_calls", 0))
        save(out / "qa_report.json", report)
        write_progress(out, report)
    return report


def _main(argv=None):
    p = argparse.ArgumentParser(description="中文題材 → 可查核研究 → 授權遊戲畫面 → 1080p 紀錄片，缺素材則阻擋")
    inputs = p.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--topic")
    inputs.add_argument("--topics-file", type=Path, help="JSON array of 1–3 topic strings")
    p.add_argument("--minutes", type=int, choices=(10,12,15), default=12)
    p.add_argument("--out", type=Path, default=Path("output/documentaries"))
    p.add_argument("--tts", choices=("edge", "kokoro"), default="edge")
    p.add_argument("--voice", default="zh-TW-YunJheNeural")
    p.add_argument("--stop-after", choices=("research", "script", "movie"), default="movie",
                   help="Explicit milestone; research/script success never means a finished film")
    args = p.parse_args(argv)
    topics = [args.topic] if args.topic is not None else json.loads(args.topics_file.read_text("utf-8"))
    if not isinstance(topics, list) or not 1 <= len(topics) <= 3 or any(not isinstance(t, str) or not t.strip() or len(t) > 500 for t in topics):
        p.error("Provide 1–3 nonempty topic strings, each <=500 characters")
    args.out.mkdir(parents=True, exist_ok=True)
    reports = []
    for topic in topics:
        slug = re.sub(r"[^\w-]", "_", topic)[:30]
        name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + slug + "-" + uuid.uuid4().hex[:8]
        report = run_pipeline(topic, args.minutes, args.out / name, args.tts, args.voice, stop_after=args.stop_after)
        reports.append(report)
        print(json.dumps(report, ensure_ascii=False), flush=True)
        if report["status"] == "CANCELLED":
            return 130
    expected = {"research": "RESEARCH_READY", "script": "SCRIPT_READY", "movie": "COMPLETE_AUTOMATED_CHECKS"}[args.stop_after]
    return 0 if all(r["status"] == expected for r in reports) else 2


def main(argv=None):
    # SIGTERM from the workflow runner gets the same journal finalization as Ctrl-C.
    # A forced SIGKILL cannot be intercepted; the last checkpoint remains available.
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
