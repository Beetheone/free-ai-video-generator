"""Commons-only rights discovery, PySceneDetect shots, frame-based semantic matching.

No YouTube scraping, stock stand-ins, generated gameplay or title-card fallbacks.
"""
import html
import math
import re
from pathlib import Path
from urllib.parse import urlsplit

from .core import Blocked, command, digest, duration, probe, save

API = "https://commons.wikimedia.org/w/api.php"


def plain(value):
    return re.sub("<[^>]*>", "", html.unescape(str(value or ""))).strip()


def licensed_record(page):
    info = (page.get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata", {})
    field = lambda name: plain(meta.get(name, {}).get("value", ""))
    license_name = field("LicenseShortName").lower()
    license_url = field("LicenseUrl")
    # Exact allowlist, not substring 'cc by' (which also accepts NC/ND).
    accepted = bool(re.fullmatch(r"cc by (?:1\.0|2\.0|2\.5|3\.0|4\.0)", license_name))
    accepted = accepted or license_name in {"cc0", "cc0 1.0", "public domain"}
    if not accepted or field("Restrictions") or not field("Artist"):
        return None
    if license_name.startswith("cc") and not license_url.startswith(("https://creativecommons.org/", "http://creativecommons.org/")):
        return None
    if license_name.startswith("cc by ") and urlsplit(license_url).path.rstrip("/") != "/licenses/by/" + license_name.split()[-1]:
        return None
    if license_name.startswith("cc0") and urlsplit(license_url).path.rstrip("/") != "/publicdomain/zero/1.0":
        return None
    if not info.get("descriptionurl", "").startswith("https://commons.wikimedia.org/wiki/File:"):
        return None
    url = info.get("url", "")
    if urlsplit(url).hostname != "upload.wikimedia.org" or not url.lower().endswith((".webm", ".ogv", ".mp4")):
        return None
    size = info.get("size", 0)
    if not isinstance(size, int) or not 10000 <= size <= 100_000_000:
        return None
    return {"title": page.get("title", ""), "url": url, "source_url": info["descriptionurl"],
            "license": field("LicenseShortName"), "license_url": license_url,
            "creator": field("Artist"), "credit": field("Credit"), "description": field("ImageDescription"),
            "metadata_evidence": meta, "declared_size": size, "rights_basis": "Wikimedia Commons file-page metadata; not an independent legal guarantee"}


def detect_shots(path, max_seconds=1200):
    from scenedetect import ContentDetector, detect
    media = probe(path)
    seconds = float(media["format"]["duration"])
    video = next((s for s in media["streams"] if s["codec_type"] == "video"), None)
    if not video or seconds > max_seconds or video.get("width", 0) * video.get("height", 0) > 3840*2160:
        raise Blocked("FOOTAGE_BUDGET", "Footage is too long, too large or has no video stream")
    scenes = detect(str(path), ContentDetector(threshold=27), show_progress=False, start_in_scene=True)
    bounds = [(a.get_seconds(), b.get_seconds()) for a, b in scenes] or [(0, seconds)]
    shots = []
    for a, b in bounds:
        # Never cross detected cuts; no repeated or frozen frames to stretch material.
        while b-a >= 2:
            end = min(a+8, b)
            shots.append({"start": round(a, 4), "end": round(end, 4)})
            a = end
    return shots


class Library:
    def __init__(self, web, model, out):
        self.web, self.model, self.out = web, model, out
        self.root = out / "footage"
        self.root.mkdir(exist_ok=True)
        self.records, self.shots, self.errors, self.queries, self.used = [], [], [], set(), set()
        self.downloaded = 0
        self.max_download = 600_000_000

    def report(self):
        save(self.out / "media_sources.json", {"records": self.records, "errors": self.errors,
             "queries": sorted(self.queries), "downloaded_bytes": self.downloaded,
             "excluded": "NC, ND, SA, missing/ambiguous licenses, restrictions, non-gameplay and unmatched footage"})

    def search(self, queries):
        for q in queries:
            if q in self.queries or len(self.queries) >= 18 or len(self.records) >= 12:
                continue
            self.queries.add(q)
            try:
                data = self.web.json(API, {"action": "query", "format": "json", "generator": "search",
                    "gsrsearch": q + " filetype:video", "gsrnamespace": 6, "gsrlimit": 8,
                    "prop": "imageinfo", "iiprop": "url|size|extmetadata"})
                for page in data.get("query", {}).get("pages", {}).values():
                    rec = licensed_record(page)
                    if not rec or rec["url"] in {r["url"] for r in self.records}:
                        continue
                    if len(self.records) >= 12 or self.downloaded + rec["declared_size"] > self.max_download:
                        break
                    # Count transferred bytes even when decoding later fails.
                    raw, _ = self.web.get(rec["url"], limit=min(100_000_000, self.max_download-self.downloaded))
                    self.downloaded += len(raw)
                    key = digest(raw)
                    if key in {r["sha256"] for r in self.records}:
                        continue
                    path = self.root / (key[:20] + Path(rec["url"]).suffix)
                    path.write_bytes(raw)
                    rec.update({"id": key[:20], "sha256": key, "path": str(path), "seconds": duration(path), "discovery_query": q})
                    shots = detect_shots(path)
                    self.records.append(rec)
                    for j, shot in enumerate(shots):
                        self.shots.append({**shot, "id": f"{rec['id']}-{j}", "asset_id": rec["id"], "path": str(path)})
            except (Blocked, ValueError, RuntimeError) as exc:
                self.errors.append({"query": q, "error": str(exc)[:400]})
            finally:
                self.report()

    def match(self, scene, seconds):
        if not math.isfinite(seconds) or seconds <= 0:
            raise Blocked("AUDIO_INVALID", "Narration duration is invalid")
        self.search(scene["footage_queries"])
        chosen, covered = [], 0.0
        available = [s for s in self.shots if s["id"] not in self.used]
        by_id = {r["id"]: r for r in self.records}
        tokens = set(re.findall(r"[a-z0-9]+", scene["visual_need"].lower()))
        # Text only orders candidates; it can NEVER approve a match without image inspection.
        def priority(shot):
            rec = by_id.get(shot["asset_id"], {})
            description = rec.get("title", "") + " " + rec.get("description", "") + " " + rec.get("discovery_query", "")
            return len(tokens & set(re.findall(r"[a-z0-9]+", description.lower())))
        available.sort(key=priority, reverse=True)
        # Bounded visual analysis: stop rather than silently select an unrelated clip.
        for shot in available[:24]:
            frames = []
            for i, fraction in enumerate((0.15, 0.5, 0.85)):
                frame = self.root / f"{shot['id']}-{i}.jpg"
                if not frame.exists():
                    at = shot["start"] + (shot["end"] - shot["start"]) * fraction
                    command(["ffmpeg", "-v", "error", "-y", "-ss", at, "-i", shot["path"], "-frames:v", "1", "-vf", "scale=640:-2", frame])
                frames.append(frame)
            assessment = self.model.json(
                'Inspect these THREE actual frames from a candidate interval. Compare with requested game AND event. '
                'Return {"gameplay":bool,"correct_game":bool,"event_visible":bool,"confidence":float,'
                '"observations":str,"reason":str}. Reject still slides, unrelated games, generic B-roll, '
                'menus when action is needed, claims not visibly demonstrated, and uncertain pixel-art identity. '
                'Match the whole interval conservatively; captions/metadata are not visual evidence.',
                {"visual_need": scene["visual_need"], "narration": scene["narration"], "interval": {"start": shot["start"], "end": shot["end"]}}, frames)
            save(self.root / f"match-{scene['id']}-{shot['id']}.json", assessment)
            confidence = assessment.get("confidence", 0)
            if (assessment.get("gameplay") is not True or assessment.get("correct_game") is not True
                    or assessment.get("event_visible") is not True or not isinstance(confidence, (int, float))
                    or not math.isfinite(confidence) or not 0.9 <= confidence <= 1
                    or not assessment.get("observations") or not assessment.get("reason")):
                continue
            take = min(seconds-covered, shot["end"]-shot["start"])
            chosen.append({**shot, "end": shot["start"]+take, "assessment": assessment})
            self.used.add(shot["id"])
            covered += take
            if covered >= seconds - 0.001:
                return chosen
        raise Blocked("LICENSED_RELEVANT_FOOTAGE_MISSING", f"Scene {scene['id']}: only {covered:.1f}/{seconds:.1f}s of licensed, visually matched gameplay. No MP4 released.")
