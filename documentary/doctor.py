"""Offline prerequisite diagnostics. Never prints secrets or claims service readiness."""
import argparse
import fnmatch
import importlib.util
import json
import os
import platform
import shutil
from pathlib import Path
from urllib.parse import urlsplit

from .core import save
from .production import FONT
from .settings import model_settings


def recovery(code):
    if code == "MODEL_PROVIDER_RETIRED":
        return ["GitHub officially retired GitHub Models on 2026-07-30, including the inference API.",
                "Use an active compatible text+vision provider. Gemini has a free tier where eligible; configure LLM_API_KEY securely and confirm the model/quota."]
    if code == "MODEL_PROTOCOL":
        return ["The configured HTTPS endpoint returned non-JSON instead of chat completions. Verify the API base URL and provider availability.",
                "Inspect safe media-type/body-kind diagnostics; do not parse an HTML page as model output or request duplicate keys without checking authorization."]
    if code in {"MODEL_SCHEMA", "MODEL_TRUNCATED"}:
        return ["Check the safe envelope/content diagnostic in blocker.detail; an HTTP 200 response is not proof of valid model output.",
                "Use a chat-completions text+vision model supporting JSON objects; never substitute a hard-coded story for an invalid response."]
    if code in {"MODEL_NETWORK", "NETWORK", "NETWORK_POLICY_BLOCKED"}:
        return ["Check current cloud network policy; draft changes do not apply themselves.",
                "Review and save required domains in environment settings, publish, then retry the affected operation."]
    if code in {"MODEL_UNAVAILABLE", "MODEL_CREDENTIAL_REQUIRED"}:
        return ["Check model authorization and quota using existing credentials first.",
                "If needed, configure a compatible text+vision endpoint and LLM_API_KEY securely in settings; never paste keys in chat."]
    if code == "MODEL_CONFIG":
        return ["Explicitly set LLM_BASE_URL and LLM_MODEL for the provider that issued LLM_API_KEY.",
                "Also check LLM_MAX_CALLS (1–1000) and LLM_MIN_INTERVAL (0–60 seconds); keys are never sent to an implicit provider."]
    if code == "MODEL_BUDGET":
        return ["Check LLM_MAX_CALLS and LLM_MIN_INTERVAL; wait for free quota reset or select another compatible provider.",
                "A larger paid quota is optional; no paid service is activated automatically."]
    if code in {"LICENSED_GAMEPLAY_MISSING", "LICENSED_RELEVANT_FOOTAGE_MISSING", "FOOTAGE_COVERAGE"}:
        return ["Inspect media_sources.json and frame-match assessments for rejected or missing intervals.",
                "Use a topic with available rights-cleared gameplay or obtain rights; do not substitute stock footage, reference-video clips, or title cards."]
    if code in {"VISUALS_INSUFFICIENT", "VISUALS_MISSING"}:
        return ["Inspect image_sources.json and image_tags.json: too few licensed, relevant, non-graphic archive images were found for this topic.",
                "Try a topic with more documented imagery (people, places, maps, documents). Unrelated pictures are never used as stand-ins."]
    if code in {"RESEARCH_INSUFFICIENT", "EVIDENCE_INSUFFICIENT", "EVIDENCE_INVALID", "FACT_CHECK_FAILED", "SCRIPT_AUDIT_FAILED"}:
        return ["Inspect research.json, evidence_draft.json, evidence_audit.json and script_audit.json as applicable.",
                "Resolve source availability or contradictory evidence before production; do not mark unsupported claims as verified."]
    if code in {"TTS_UNAVAILABLE", "KOKORO_DEPENDENCY"}:
        return ["Check the voice service network route; alternatively install the documented Kokoro CPU dependencies/model.",
                "Neither a sine-wave test nor successful audio encoding validates natural Chinese narration."]
    if code in {"MEDIA_TIMEOUT", "RUN_INTERRUPTED"}:
        return ["Inspect current_stage, progress and completed_stages; partial files are not a finished film.",
                "Run again in a new output directory after restoring sufficient runtime/resources; no unchecked partial job is auto-resumed."]
    if code in {"RENDER_QA_FAILED", "NARRATION_RUNTIME", "CAPTION_READABILITY", "CAPTION_TIMING"}:
        return ["Inspect narration.json and media_qa.json; preserve the quality gates.",
                "Correct the cause and rerun; do not use loops, slowed audio or filler to pass the runtime requirement."]
    return ["Inspect the report for the failed stage and its saved artifacts before rerunning."]


def diagnose(engine="edge", policy_path=Path("/etc/codex/network-policy.json")):
    key_names = ("LLM_API_KEY", "GH_TOKEN", "GITHUB_TOKEN")
    credentials = {name: bool(os.getenv(name)) for name in key_names}
    tools = {name: bool(shutil.which(name)) for name in ("ffmpeg", "ffprobe")}
    modules = {name: importlib.util.find_spec(name) is not None for name in ("requests", "PIL", "edge_tts", "scenedetect", "trafilatura", "opencc")}
    if engine == "kokoro":
        modules.update({name: importlib.util.find_spec(name) is not None for name in ("kokoro", "soundfile", "misaki")})
    font = Path(FONT).is_file()
    policy, policy_error = None, None
    if policy_path.is_file():
        try:
            parsed = json.loads(policy_path.read_text())
            if parsed.get("version") == 1:
                policy = parsed.get("http_network_policy")
        except (ValueError, OSError):
            policy_error = "Policy snapshot is unreadable or malformed"
    hosts = [] if policy is None else [e["host"] for e in policy.get("egress_rules", []) if isinstance(e, dict) and isinstance(e.get("host"), str)]
    config_error = None
    try:
        base, name = model_settings()
    except (ValueError, TypeError, OSError):
        base, name = "", ""
        config_error = "Invalid non-secret provider configuration"
    model_host = urlsplit(base).hostname
    services = {"model": [model_host], "research": ["www.bing.com"],
                "footage": ["commons.wikimedia.org", "upload.wikimedia.org"],
                "voice": ["speech.platform.bing.com"] if engine == "edge" else ["huggingface.co"],
                "pull_request": ["api.github.com"]}
    results = []
    for service, domains in services.items():
        for domain in domains:
            allowed = None
            if policy is not None and domain:
                if policy.get("type") == "restricted":
                    allowed = any(fnmatch.fnmatchcase(domain, host) for host in hosts)
                elif policy.get("type") == "disabled":
                    allowed = False
                elif policy.get("type") == "unrestricted":
                    allowed = True
            results.append({"service": service, "hostname": domain, "startup_policy_allows": allowed,
                            "live_operation_tested": False})
    missing = [n for n, ok in {**tools, **modules, "Noto CJK font": font}.items() if not ok]
    denied = [r["hostname"] for r in results if r["startup_policy_allows"] is False]
    if not credentials["LLM_API_KEY"]:
        missing.append("LLM_API_KEY for the configured model provider; a GitHub token is not a Gemini API key")
    if not base or not model_host:
        missing.append("LLM_BASE_URL explicitly selecting an active HTTPS text+vision API provider")
    if not name:
        missing.append("LLM_MODEL supported by the chosen provider")
    if config_error:
        missing.append(config_error)
    if model_host in {"models.github.ai", "models.inference.ai.azure.com"}:
        missing.append("active model provider; GitHub Models inference retired on 2026-07-30")
    blocked = bool(missing or denied)
    return {"status": "PREREQUISITES_BLOCKED" if blocked else "PRECHECKS_PASS_SERVICE_TESTS_REQUIRED",
            "scope": "Metadata and startup policy snapshot only. Not a current runtime policy or external service readiness proof.",
            "python": platform.python_version(), "tools": tools, "modules": modules, "cjk_font": font,
            "model_provider": {"hostname": model_host, "model": name or None, "repository_config": "config/model.json"},
            "credential_variable_presence": credentials, "policy_snapshot_available": policy is not None,
            "policy_snapshot_error": policy_error, "services": results, "missing_prerequisites": missing,
            "domains_denied_by_startup_snapshot": denied,
            "next_actions": recovery("NETWORK_POLICY_BLOCKED") if denied else ["Run the real topic pipeline to validate model authorization, research, rights-cleared footage and narration."]}


def main(argv=None):
    p = argparse.ArgumentParser(description="Inspect prerequisites without network requests or credential values")
    p.add_argument("--tts", choices=("edge", "kokoro"), default="edge")
    p.add_argument("--out", type=Path, default=Path("output/environment-diagnosis.json"))
    args = p.parse_args(argv)
    report = diagnose(args.tts)
    save(args.out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "PREREQUISITES_BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
