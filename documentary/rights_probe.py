"""Inspect real Commons permissions without downloading or approving gameplay."""
import argparse
from collections import Counter
from pathlib import Path

from .core import Blocked, Web, save
from .footage import API, licensed_record, plain
from .reporting import read_json


def inspect_rights(web, queries, out):
    candidates, seen, errors, rejected = [], set(), [], 0
    rejected_licenses = Counter()
    for query in queries[:3]:
        try:
            data = web.json(API, {"action": "query", "format": "json", "generator": "search",
                "gsrsearch": query + " filetype:video", "gsrnamespace": 6, "gsrlimit": 8,
                "prop": "imageinfo", "iiprop": "url|size|extmetadata"})
            if not isinstance(data, dict) or "error" in data:
                raise Blocked("COMMONS_UNAVAILABLE", "Commons did not return a successful metadata response")
            for page in data.get("query", {}).get("pages", {}).values():
                title = page.get("title")
                if title in seen:
                    continue
                seen.add(title)
                record = licensed_record(page)
                if record is None:
                    rejected += 1
                    info = (page.get("imageinfo") or [{}])[0]
                    label = plain(info.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "")) or "MISSING"
                    rejected_licenses[label] += 1
                    continue
                candidates.append(record)
        except (Blocked, ValueError, TypeError, AttributeError) as exc:
            errors.append({"error_type": type(exc).__name__, "code": getattr(exc, "code", "COMMONS_PROTOCOL")})
    state = "CANDIDATES_REQUIRE_FRAME_MATCH" if candidates else "SOURCE_UNAVAILABLE" if errors else "NO_SUPPORTED_LICENSED_CANDIDATES"
    report = {"status": state, "provider": "Wikimedia Commons", "queries": queries[:3],
              "inspected_entries": len(seen), "rejected_entries": rejected, "candidate_count": len(candidates),
              "candidates": candidates, "errors": errors, "downloaded_bytes": 0,
              "rejected_license_names": dict(rejected_licenses),
              "visual_relevance_verified": False,
              "scope": "Metadata permission leads only. No gameplay downloaded, viewed, matched or legally guaranteed."}
    save(out / "footage_readiness.json", report)
    lines = ["# 遊戲畫面可取得性", "", f"目前搜尋入口：Wikimedia Commons；檢查 {len(seen)} 個檔案條目。", "",
             f"符合目前支援授權／檔案限制的候選：{len(candidates)}；尚未下載或辨識畫面。", ""]
    if candidates:
        lines += ["候選不代表與故事相符，正式產片仍需逐段影格檢查與完整時間覆蓋。", ""]
        lines.extend(f"- {r['title']}：{r['license']}\n  {r['source_url']}" for r in candidates)
    elif errors:
        lines.append("來源服務未完成回應，目前不能判定有沒有合法素材。")
    else:
        lines.append("這次 Commons 搜尋沒有找到符合目前支援條件的候選，並不代表全網都沒有。若要產片，還需要權利清楚且與故事相符的遊戲錄影；目前不會下載未授權影片或用無關畫面補位。")
    if rejected_licenses:
        lines += ["", "未採用檔案的授權標示（也可能受檔案大小、作者欄位等條件影響）：", ""]
        lines.extend(f"- {name}：{count} 個條目" for name, count in rejected_licenses.items())
        lines += ["", "目前只支援明確 CC BY、CC0、Public Domain，且有作者／授權證據、單檔 100 MB 以內。CC BY-SA 等其他條款尚未整合，未採用不代表該授權本身無效。"]
    (out / "FOOTAGE_GAPS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description="Check rights metadata separately from research and script quality")
    p.add_argument("--root", type=Path, default=Path("output/research"))
    args = p.parse_args(argv)
    for path in args.root.glob("*/topic.json"):
        plan = read_json(path, {})
        queries = plan.get("footage_queries", [])
        if isinstance(queries, list) and queries and all(isinstance(q, str) and 0 < len(q) <= 240 for q in queries):
            inspect_rights(Web(), queries, path.parent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
