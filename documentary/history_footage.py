"""Real moving footage from the Internet Archive, strictly licence-gated.

Only items whose Archive metadata carries an explicit CC0 / Public Domain Mark / CC BY licence URL are
used (most old newsreels have no licence field and are therefore skipped; that is deliberate). Each
accepted item is cut into short clips that join the same pool as the Commons images, so the vision
model inspects the actual pixels before any scene may use a clip. Footage is a bonus: every failure here
is recorded and the video continues with images alone.
"""
import re
from pathlib import Path
from urllib.parse import quote

from PIL import Image

from .core import Blocked, command, digest, duration, save

SEARCH = "https://archive.org/advancedsearch.php"
METADATA = "https://archive.org/metadata/"
DOWNLOAD = "https://archive.org/download/"
IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,120}")
CLIP_SECONDS = 8.0


def archive_license(url):
    """('pd'|'by', label) for an explicitly accepted licence URL, else None."""
    u = (url or "").strip().lower().replace("http://", "https://")
    if u.startswith("https://creativecommons.org/publicdomain/zero/"):
        return "pd", "CC0 1.0"
    if u.startswith("https://creativecommons.org/publicdomain/mark/"):
        return "pd", "Public Domain Mark 1.0"
    m = re.match(r"https://creativecommons\.org/licenses/by/(1\.0|2\.0|2\.5|3\.0|4\.0)(?:/|$)", u)
    if m:
        return "by", "CC BY " + m[1]
    return None


def _text(value, limit=300):
    if isinstance(value, list):
        value = "; ".join(str(v) for v in value[:3])
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(value or ""))).strip()[:limit]


def _query_terms(text):
    words = re.findall(r"[A-Za-z0-9]+", text or "")
    return " ".join(words[:6])


def pick_file(files, max_bytes=120_000_000):
    """Smallest reasonable H.264/MPEG-4 derivative; never an original of unknown codec."""
    best = None
    for f in files or []:
        name, fmt = str(f.get("name", "")), str(f.get("format", "")).lower()
        try:
            size = int(f.get("size", 0))
        except (TypeError, ValueError):
            continue
        if not name.lower().endswith(".mp4") or "/" in name or not 50_000 <= size <= max_bytes:
            continue
        if not ("h.264" in fmt or "mpeg4" in fmt or "mpeg-4" in fmt):
            continue
        if best is None or size > best[0] and size <= 60_000_000:
            best = (size, name)
    return best[1] if best else None


def _frame(src, at, dest, width):
    command(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", src, "-frames:v", "1", "-vf", f"scale={width}:-2", dest], timeout=120)


def make_clips(src, key, out, *, max_clips=5, clip_seconds=CLIP_SECONDS):
    """Cut evenly spread clips; return [{id, path, preview, still, start, seconds}]."""
    total = duration(src)
    if total < 3:
        return []
    clips_dir, previews = out / "footage" / "clips", out / "footage" / "previews"
    clips_dir.mkdir(parents=True, exist_ok=True)
    previews.mkdir(parents=True, exist_ok=True)
    length = min(clip_seconds, total)
    count = 1 if total <= clip_seconds + 2 else min(max_clips, int((total - 2) // (clip_seconds + 4)) + 1)
    starts = [0.0] if count == 1 else [round(1 + (total - 2 - length) * i / (count - 1), 2) for i in range(count)]
    records = []
    for start in starts:
        cid = digest(f"{key}:{start}".encode())[:16]
        clip = clips_dir / f"{cid}.mp4"
        command(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-t", f"{length:.2f}", "-i", src, "-an",
                 "-vf", "fps=24,scale=1920:1080:force_original_aspect_ratio=decrease:flags=bicubic,setsar=1",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", clip], timeout=300)
        got = duration(clip)
        if got < 2:
            continue
        a, b, c = previews / f"{cid}-a.jpg", previews / f"{cid}-b.jpg", out / "footage" / f"{cid}-still.jpg"
        _frame(clip, got * 0.25, a, 640)
        _frame(clip, got * 0.75, b, 640)
        _frame(clip, got * 0.5, c, 1280)
        ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
        sheet = Image.new("RGB", (ia.width + ib.width, max(ia.height, ib.height)))
        sheet.paste(ia, (0, 0))
        sheet.paste(ib, (ia.width, 0))
        preview = previews / f"{cid}.jpg"
        sheet.save(preview, "JPEG", quality=80)
        a.unlink(missing_ok=True)
        b.unlink(missing_ok=True)
        records.append({"id": cid, "path": str(clip), "preview": str(preview), "still": str(c), "start": start, "seconds": got})
    return records


def collect(web, pool, plan, out, *, max_items=6, max_total_bytes=360_000_000, delay=0.25):
    """Add licensed Archive clips to the pool. Never raises: returns a small report dict."""
    import time
    report = {"queries": [], "items": [], "errors": [], "clips": 0, "downloaded_bytes": 0}
    out = Path(out)
    queries = []
    for q in [plan.get("english_topic", "")] + list(plan.get("image_queries", []))[:2]:
        t = _query_terms(q)
        if t and t not in queries:
            queries.append(t)
    seen, candidates = set(), []
    for term in queries[:3]:
        report["queries"].append(term)
        try:
            data = web.json(SEARCH, {"q": f"({term}) AND mediatype:movies", "fl[]": ["identifier", "title", "licenseurl"],
                                      "rows": 30, "page": 1, "output": "json"})
            for doc in data.get("response", {}).get("docs", []):
                ident = doc.get("identifier")
                if isinstance(ident, str) and IDENT.fullmatch(ident) and ident not in seen and archive_license(_text(doc.get("licenseurl"), 200)):
                    seen.add(ident)
                    candidates.append(ident)
        except (Blocked, ValueError, AttributeError, TypeError) as exc:
            report["errors"].append({"query": term, "error": str(exc)[:160]})
        if delay:
            time.sleep(delay)
    for ident in candidates:
        if len(report["items"]) >= max_items or report["downloaded_bytes"] >= max_total_bytes:
            break
        try:
            meta = web.json(METADATA + quote(ident))
            md = meta.get("metadata", {})
            lic = archive_license(_text(md.get("licenseurl"), 200))
            if not lic:
                continue
            kind, label = lic
            creator = _text(md.get("creator"), 120)
            if kind == "by" and not creator:
                report["errors"].append({"id": ident, "error": "CC BY item without creator"})
                continue
            name = pick_file(meta.get("files"), min(120_000_000, max_total_bytes - report["downloaded_bytes"]))
            if not name:
                continue
            raw, _ = web.get(DOWNLOAD + quote(ident) + "/" + quote(name), limit=120_000_000)
            report["downloaded_bytes"] += len(raw)
            src = out / "footage" / f"{digest(ident.encode())[:12]}.mp4"
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_bytes(raw)
            made = make_clips(str(src), ident, out)
            src.unlink(missing_ok=True)
            for clip in made:
                pool.add_record({**clip, "title": _text(md.get("title"), 140) or ident, "source_url": "https://archive.org/details/" + ident,
                                 "license": label, "license_url": _text(md.get("licenseurl"), 200), "license_kind": kind,
                                 "creator": creator or "Unknown", "credit": "", "description": _text(md.get("description"), 400),
                                 "categories": "", "width": 1920, "height": 1080, "mime": "video/mp4", "media": "video",
                                 "rights_basis": "Internet Archive item metadata licence URL; not an independent legal guarantee",
                                 "discovery": "archive.org:" + ident})
            report["clips"] += len(made)
            report["items"].append({"id": ident, "title": _text(md.get("title"), 100), "license": label, "clips": len(made)})
        except (Blocked, ValueError, OSError, AttributeError, TypeError, KeyError) as exc:
            report["errors"].append({"id": ident, "error": str(exc)[:160]})
        if delay:
            time.sleep(delay)
    save(out / "footage_sources.json", report)
    return report
