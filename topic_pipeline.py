"""Topic-only gaming documentary research gate; supports Chinese and English titles.
Produces bilingual research leads. It does not pretend to have rendered a video.
"""
import argparse
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("agent_output")
CJK = re.compile(r"[\u3400-\u9fff]")
# Small curated aliases boost bilingual retrieval; unknown topics still work in Chinese.
ALIASES = {
    "寶可夢": "Pokemon", "精靈寶可夢": "Pokemon", "神奇寶貝": "Pokemon",
    "夢幻": "Mew", "卡車": "truck", "紅綠": "Red Green",
    "瑪利歐": "Mario", "馬力歐": "Mario", "速通": "speedrun",
    "艾爾登法環": "Elden Ring", "薩爾達": "Zelda", "當機": "crash",
    "漏洞": "glitch", "遊戲": "game", "世界紀錄": "world record",
}

def english_hints(topic):
    parts = [english for zh, english in ALIASES.items() if zh in topic]
    parts += re.findall(r"[A-Za-z][A-Za-z0-9'-]*", topic)
    return " ".join(dict.fromkeys(parts)).strip()

def fetch_rss(query, locale, limit=15):
    if locale == "zh-TW":
        region = "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    else:
        region = "&hl=en-US&gl=US&ceid=US:en"
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(query) + region
    request = urllib.request.Request(url, headers={"User-Agent": "GameDocResearch/0.3"})
    with urllib.request.urlopen(request, timeout=18) as response:
        root = ET.fromstring(response.read(1500000))
    return [{
        "title": item.findtext("title", "").strip(),
        "url": item.findtext("link", "").strip(),
        "date": item.findtext("pubDate", "").strip(),
        "language": locale,
        "verified": False
    } for item in root.findall(".//item")[:limit] if item.findtext("link")]

def research(topic):
    is_chinese = bool(CJK.search(topic))
    queries = [(topic + (" 遊戲 事件" if is_chinese else " game history"), "zh-TW" if is_chinese else "en-US")]
    if is_chinese:
        hints = english_hints(topic)
        if hints:
            queries.append((hints + " video game history", "en-US"))
        else:
            queries.append((topic, "en-US"))
    else:
        queries.append((topic + " 遊戲 歷史", "zh-TW"))
    results, errors, seen = [], [], set()
    for query, locale in queries:
        try:
            for lead in fetch_rss(query, locale):
                key = lead["url"]
                if key not in seen:
                    results.append(lead)
                    seen.add(key)
        except Exception as exc:
            errors.append({"query": query, "locale": locale, "error": str(exc)[:200]})
    return results, queries, errors

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True, help="中文、English, or mixed gaming topic")
    parser.add_argument("--minutes", type=int, default=12)
    args = parser.parse_args()
    if not args.topic.strip():
        parser.error("topic must not be blank")
    OUT.mkdir(exist_ok=True)
    leads, queries, errors = research(args.topic)
    report = {
        "topic": args.topic,
        "input_language": "Chinese_or_mixed" if CJK.search(args.topic) else "non_Chinese",
        "target_minutes": args.minutes,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "search_queries": [{"query": query, "locale": locale} for query, locale in queries],
        "research_leads": leads,
        "search_errors": errors,
        "structure": ["hook", "origin", "characters", "challenge", "evidence", "reversal", "resolution"],
        "needs": ["fact_checked_script", "licensed_gameplay_footage", "narration", "visual_matching", "render_qa"],
        "status": "BLOCKED_RESEARCH_OR_ASSETS_REQUIRED",
        "notice": "RSS items are unverified leads. Alias keywords are NOT full translation. This run does not produce an MP4."
    }
    (OUT / "topic_plan.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"topic": args.topic, "leads": len(leads), "searches": len(queries), "errors": len(errors), "status": report["status"]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
