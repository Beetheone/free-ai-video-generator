"""Small, real service checks; no documentary or factual-quality claim."""
import argparse
import json
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

from PIL import Image, ImageDraw

from .core import Blocked, Model, Web, command, save
from .production import stamp, synthesize

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"


def check_model(out):
    model = Model()
    # Stop BEFORE sending a key if old Actions Variables/Secrets override the
    # user's selected provider. Never test a Gemini key against an old GPT URL.
    if model.base != GEMINI_BASE or not model.name.startswith("gemini-"):
        raise Blocked("MODEL_PROVIDER_MISMATCH", "Gemini selected but effective LLM_BASE_URL / LLM_MODEL still target another provider or API path; update or remove old Actions overrides")
    image = Image.new("RGB", (160, 80), "red")
    ImageDraw.Draw(image).rectangle((80, 0, 159, 79), fill="blue")
    path = out / "vision-test.jpg"
    image.save(path)
    result = model.json(
        "Environment test only. Read the attached synthetic image. Return JSON "
        "with left_color and right_color as lowercase English color names, "
        "and echo as an exact copy of the supplied echo field.",
        {"echo": "繁體中文環境確認"}, images=[path])
    if result != {"left_color": "red", "right_color": "blue", "echo": "繁體中文環境確認"}:
        raise Blocked("MODEL_SMOKE_FAILED", "Text/vision JSON check did not match the known synthetic image and Traditional Chinese input; model output withheld")
    return {"hostname": urlsplit(model.base).hostname, "model": model.name,
            "inference_calls": model.calls, "usage": model.usage,
            "usage_unavailable_calls": model.usage_unavailable_calls,
            "scope": "One synthetic two-color image and Chinese echo, not gameplay recognition, research quality or a daily quota guarantee"}


def check_search(_out):
    raw, _ = Web().get("https://www.bing.com/search", params={"q": "Pokemon Red Green Mew truck rumor", "format": "rss"})
    root = ElementTree.fromstring(raw)
    count = len(root.findall("./channel/item"))
    if root.tag != "rss" or not count:
        raise Blocked("SEARCH_UNAVAILABLE", "Bing did not return nonempty RSS search results")
    return {"search_results": count, "scope": "Search connectivity only; article bodies and claims not verified"}


def check_commons(_out):
    body = Web().json("https://commons.wikimedia.org/w/api.php", params={
        "action": "query", "format": "json", "meta": "siteinfo", "siprop": "general"})
    if not isinstance(body.get("query", {}).get("general", {}).get("sitename"), str):
        raise Blocked("COMMONS_UNAVAILABLE", "Commons did not return site metadata")
    return {"scope": "Commons API connectivity only; no licensed or relevant gameplay acquired"}


def check_voice(out):
    text = "這是繁體中文旁白測試，遊戲紀錄片環境正在確認。"
    audio = synthesize(text, out / "voice-sample.mp3")
    path = Path(audio["path"])
    command(["ffmpeg", "-v", "error", "-i", path, "-f", "null", "-"], timeout=30)
    (out / "voice-sample.srt").write_text("\n".join(
        f"{i}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}\n"
        for i, c in enumerate(audio["cues"], 1)), encoding="utf-8")
    return {"voice": "zh-TW-YunJheNeural", "seconds": audio["seconds"],
            "caption_count": len(audio["cues"]), "sample": path.name,
            "scope": "Actual TTS audio fully decoded and captions validated; naturalness requires listening"}


def verify(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    report = {"status": "CHECKING", "scope": "Service smoke tests only; no documentary produced",
              "checks": {}}
    for name, check in (("gemini_text_vision", check_model), ("search", check_search),
                        ("commons", check_commons), ("taiwan_voice", check_voice)):
        try:
            report["checks"][name] = {"status": "PASS", **check(out)}
        except Blocked as exc:
            report["checks"][name] = {"status": "BLOCKED", "code": exc.code, "detail": exc.detail}
        except Exception as exc:
            # SDK and XML errors may contain credential-bearing request details.
            report["checks"][name] = {"status": "BLOCKED", "code": "ENVIRONMENT_CHECK_ERROR", "detail": type(exc).__name__}
        save(out / "report.json", report)
    report["status"] = "SERVICE_CHECKS_PASS" if all(c["status"] == "PASS" for c in report["checks"].values()) else "BLOCKED"
    save(out / "report.json", report)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description="Verify selected Gemini, search, Commons and real Taiwan TTS with small requests")
    p.add_argument("--out", type=Path, default=Path("output/environment-checks") / uuid.uuid4().hex)
    args = p.parse_args(argv)
    report = verify(args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "SERVICE_CHECKS_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
