"""History mode: licensed archive images, hook-first script rules, music and packaging.

Only light dependencies (requests/Pillow via core) are imported here so the logic can be
tested without the research stack. Nothing in this module invents rights, pictures or
claims: every image comes from Wikimedia Commons metadata that passes an explicit
allowlist, is inspected by the vision model, and is credited in the output.
"""
import math
import re
import time
from pathlib import Path

from PIL import Image

from .core import Blocked, digest, save
from .footage import plain

COMMONS = "https://commons.wikimedia.org/w/api.php"
WIKIPEDIA = "https://en.wikipedia.org/w/api.php"

HISTORY_SECTIONS = [
    "開場鉤子：前三個場景先講出最反直覺的結局或矛盾（有證據支持），立刻丟出一個讓人想知道答案的問題，絕不寒暄、不自我介紹、不從年份開始；最後一句留下懸念",
    "背景與主角：用一個具體的人和他當時面對的處境，說明事情為什麼會發生；用畫面感的細節取代年表；最後一句拋出新的疑問",
    "事件升級：事情如何一步步失控或出人意料；每個場景只推進一件事；結尾留下尚未解答的懸念",
    "轉折與反常細節：最讓人意外的證據或反轉；保留有據可查的數字與人名；用『但是』『問題是』推進",
    "代價、爭議與真相：各方說法、證據不足之處與後果；有爭議的說法必須明說是爭議；回答開場拋出的問題",
    "餘波與回扣開場：事件的長期影響，回到開場的畫面或矛盾做收尾，留下一句值得記住的觀察，不喊口號",
]

HISTORY_INSTRUCTION = (
    'Write ONE chapter of an ORIGINAL Traditional Chinese history video narration for a general audience. '
    'It must hold attention: spoken, concrete, vivid, short sentences; one idea per scene; people, places, numbers and '
    'stakes instead of a timeline; end every chapter on an open question the next chapter answers. '
    'No greetings, no "今天要跟大家聊", no filler, no moralizing. '
    'Use ONLY supplied supported claims; qualify rumors and disputed points explicitly. Do not copy source prose or '
    'imitate an existing creator. No invented dialogue, quotes, dates, numbers or motives. '
    'Return {"scenes":[{"narration":str,"claim_ids":["C1"],'
    '"visual_need":"precise English description of the historical photograph, painting, map or document that should be on screen",'
    '"footage_queries":["1-2 English Wikimedia Commons search queries naming the exact subject, people, place or era"]}]}. '
    'Each scene 40–120 Chinese characters. Write 8–14 scenes and aim for target_characters: one supported claim can carry '
    '2–4 scenes if you slow down, set the scene, explain what was at stake and voice the question a viewer would ask, '
    'but every sentence must stay traceable to the claims you cite in claim_ids (use ONLY IDs that exist in the ledger; every scene needs at least one). '
    'Never repeat any earlier sentence word for word (see previous_narration); a callback to the opening must be reworded. '
    'If evidence cannot sustain the requested length, return fewer scenes rather than invent.'
)

DISCLOSURE = ("本片使用 AI 輔助研究、撰稿與配音，畫面為授權的歷史圖片與資料；"
              "部分圖片為同時代或同主題的資料圖片，未必拍攝於該事件當下。內容經自動引句審核，非人工查證。")


def _strings(value, minimum, maximum, limit=240):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum or any(not isinstance(s, str) or not s.strip() or len(s) > limit for s in value):
        raise Blocked("MODEL_SCHEMA", "Expected a bounded list of non-empty strings")
    return [s.strip() for s in value]


def plan_history(model, topic):
    result = model.json(
        'Translate and disambiguate this history topic for research and image search. '
        'Return {"english_topic":str,"era":"short English period/place label","queries_zh":[2-3 Traditional Chinese queries],'
        '"queries_en":[2-3 English queries],"image_queries":[4-6 English Wikimedia Commons queries: the exact event, the main people, '
        'the place, typical objects/technology of the period, contemporary maps or documents],'
        '"reference_titles_en":[0-2 canonical English Wikipedia article titles closely relevant to the topic],'
        '"candidate_urls":[0-3 likely primary documentation URLs such as archives or official records]}. '
        'These are UNVERIFIED search leads that will be fetched; never treat guessed titles or URLs as evidence. '
        'Queries must seek primary sources, contemporary reports, scholarly corrections and timelines.',
        {"topic": topic})
    if not isinstance(result.get("english_topic"), str) or not result["english_topic"].strip():
        raise Blocked("MODEL_SCHEMA", "Translation missing english_topic")
    for key, lo, hi in (("queries_zh", 2, 3), ("queries_en", 2, 3), ("image_queries", 3, 6)):
        result[key] = _strings(result.get(key), lo, hi)
    result["reference_titles_en"] = _strings(result.get("reference_titles_en", []), 0, 2)
    result["candidate_urls"] = _strings(result.get("candidate_urls", []), 0, 3)
    if not re.search("[a-zA-Z]", result["english_topic"]):
        raise Blocked("TRANSLATION", "No English topic expansion returned")
    result["original_topic"] = topic
    # Shared research helpers read plan["game"] as an extra ranking keyword.
    result["game"] = result["english_topic"]
    result["footage_queries"] = result["image_queries"]
    # A 10–15 minute narration needs far more atomic, corroborated facts than the game pipeline's default.
    result["quotes_per_source"] = 12
    result["ledger_target"] = "18–28"
    return result


# ---------------------------------------------------------------- licenses

def license_kind(name):
    """Return 'pd' or 'by' for an explicitly accepted Commons license label, else None."""
    n = re.sub(r"\s+", " ", (name or "").strip().lower())
    if not n or any(bad in n for bad in ("non-free", "nonfree", "fair use", " nc", " nd", "-sa", " sa ", "sa 4", "sa 3", "sa 2", "sa 1")):
        return None
    if re.fullmatch(r"cc by (?:1\.0|2\.0|2\.5|3\.0|4\.0)", n):
        return "by"
    if n in {"cc0", "cc0 1.0", "public domain"} or n.startswith("public domain") or re.match(r"pd[\s-]", n) or n == "pd":
        return "pd"
    return None


def _license_url_ok(name, url):
    n = name.lower()
    if n.startswith("cc by "):
        return url.startswith(("https://creativecommons.org/licenses/by/", "http://creativecommons.org/licenses/by/"))
    return True


def licensed_media_record(page, kinds=("image/jpeg", "image/png"), min_width=1000, min_pixels=800_000, max_bytes=60_000_000):
    """Strict Commons file-page metadata filter shared by images and audio."""
    info = (page.get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata", {})
    field = lambda n: plain(meta.get(n, {}).get("value", ""))
    name = field("LicenseShortName")
    kind = license_kind(name)
    if kind is None or field("Restrictions") or field("NonFree").lower() in {"true", "1", "yes"}:
        return None
    if info.get("mime") not in kinds:
        return None
    if not info.get("descriptionurl", "").startswith("https://commons.wikimedia.org/wiki/File:"):
        return None
    license_url = field("LicenseUrl")
    if kind == "by" and not _license_url_ok(name, license_url):
        return None
    creator = field("Artist")
    credit = field("Credit")
    if kind == "by" and not creator:
        return None
    if kind == "pd" and not (creator or credit or field("ImageDescription")):
        return None
    size = info.get("size", 0)
    if not isinstance(size, int) or not 5_000 <= size <= max_bytes:
        return None
    width, height = info.get("width", 0), info.get("height", 0)
    if info.get("mime", "").startswith("image/"):
        if not isinstance(width, int) or not isinstance(height, int) or width < min_width or width * height < min_pixels:
            return None
    url = info.get("thumburl") or info.get("url", "")
    from urllib.parse import urlsplit
    if urlsplit(url).hostname != "upload.wikimedia.org":
        return None
    return {"title": page.get("title", ""), "url": url, "source_url": info["descriptionurl"], "license": name,
            "license_url": license_url, "license_kind": kind, "creator": creator or credit or "Unknown author",
            "credit": credit, "description": field("ImageDescription")[:400], "categories": field("Categories")[:300],
            "width": width, "height": height, "mime": info.get("mime"),
            "rights_basis": "Wikimedia Commons file-page metadata; not an independent legal guarantee"}


# ---------------------------------------------------------------- image pool

class ImagePool:
    """Licensed Commons images, inspected by the vision model before any scene may use them."""

    MAX_QUERIES = 48
    MAX_IMAGES = 90

    def __init__(self, web, model, out, *, delay=0.25):
        self.web, self.model, self.out, self.delay = web, model, Path(out), delay
        self.root = self.out / "images"
        self.previews = self.out / "image_previews"
        self.root.mkdir(parents=True, exist_ok=True)
        self.previews.mkdir(parents=True, exist_ok=True)
        self.records, self.errors, self.queries, self.urls, self.hashes = [], [], set(), set(), set()
        self.downloaded = 0
        self.max_download = 500_000_000

    # -- discovery
    def report(self):
        save(self.out / "image_sources.json", {"records": [{k: v for k, v in r.items() if k != "path"} for r in self.records],
             "errors": self.errors, "queries": sorted(self.queries), "downloaded_bytes": self.downloaded,
             "excluded": "NC, ND, SA, non-free, missing license evidence, restrictions, small or non-JPEG/PNG files"})

    def _pause(self):
        if self.delay:
            time.sleep(self.delay)

    def _ingest(self, pages, label):
        for page in pages:
            if len(self.records) >= self.MAX_IMAGES or self.downloaded >= self.max_download:
                return
            record = licensed_media_record(page)
            if not record or record["url"] in self.urls:
                continue
            self.urls.add(record["url"])
            try:
                raw, _ = self.web.get(record["url"], limit=min(20_000_000, self.max_download - self.downloaded))
                self.downloaded += len(raw)
                key = digest(raw)
                if key in self.hashes:
                    continue
                path = self.root / (key[:16] + ".jpg")
                preview = self.previews / (key[:16] + ".jpg")
                self._store(raw, path, preview)
            except (Blocked, OSError, ValueError, Image.DecompressionBombError) as exc:
                self.errors.append({"title": record["title"], "error": str(exc)[:200]})
                continue
            self.hashes.add(key)
            record.update({"id": key[:16], "sha256": key, "path": str(path), "preview": str(preview), "discovery": label})
            self.records.append(record)
            self._pause()

    @staticmethod
    def _store(raw, path, preview):
        from io import BytesIO
        im = Image.open(BytesIO(raw))
        im.load()
        if im.width * im.height > 60_000_000:
            raise ValueError("image too large")
        im = im.convert("RGB")
        if im.width > 2400:
            im = im.resize((2400, round(im.height * 2400 / im.width)), Image.LANCZOS)
        im.save(path, "JPEG", quality=92)
        small = im.copy()
        small.thumbnail((640, 640))
        small.save(preview, "JPEG", quality=80)

    def seed_from_articles(self, titles):
        """Editor-chosen images of the relevant English Wikipedia articles (Commons-hosted only)."""
        for title in titles[:2]:
            try:
                data = self.web.json(WIKIPEDIA, {"action": "query", "format": "json", "titles": title, "prop": "images", "imlimit": 40, "redirects": 1})
                files = [i["title"] for p in data.get("query", {}).get("pages", {}).values() for i in p.get("images", [])
                         if i.get("title", "").lower().endswith((".jpg", ".jpeg", ".png"))]
                for start in range(0, len(files), 15):
                    batch = files[start:start + 15]
                    pages = self.web.json(COMMONS, {"action": "query", "format": "json", "titles": "|".join(batch),
                                                     "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1920})
                    self._ingest(pages.get("query", {}).get("pages", {}).values(), "article:" + title)
            except (Blocked, ValueError, AttributeError, TypeError) as exc:
                self.errors.append({"article": title, "error": str(exc)[:200]})
            finally:
                self.report()

    def search(self, queries):
        for q in queries:
            if q in self.queries or len(self.queries) >= self.MAX_QUERIES or len(self.records) >= self.MAX_IMAGES:
                continue
            self.queries.add(q)
            try:
                data = self.web.json(COMMONS, {"action": "query", "format": "json", "generator": "search",
                    "gsrsearch": q + " filetype:bitmap", "gsrnamespace": 6, "gsrlimit": 12,
                    "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1920})
                self._ingest(data.get("query", {}).get("pages", {}).values(), q)
            except (Blocked, ValueError, AttributeError, TypeError) as exc:
                self.errors.append({"query": q, "error": str(exc)[:200]})
            finally:
                self.report()
                self._pause()

    # -- vision inspection (pixels only; Commons text is never visual evidence)
    def tag(self, plan):
        pending = [r for r in self.records if "tags" not in r]
        for start in range(0, len(pending), 6):
            batch = pending[start:start + 6]
            result = self.model.json(
                'Inspect these actual images for a history video. Return {"images":[{"id":str,"depicts":"one English sentence of what is VISIBLE",'
                '"kind":"photograph|painting|map|diagram|document|other","relevance":0..1,"graphic":bool,"modern_overlay":bool,"impact":0..1}]} '
                'in the same order. relevance = how clearly the PIXELS relate to the topic (a visible, specific subject), not the file name. '
                'graphic = gore, corpses, nudity or distressing injury. modern_overlay = watermark, advertisement, UI or modern text covering the picture. '
                'impact = strength as a thumbnail (clear subject, contrast, emotion). Commons titles/descriptions are leads, never evidence. '
                'Do NOT name a specific real person unless a caption or text inside the image visibly says so.',
                {"topic": {k: plan.get(k) for k in ("original_topic", "english_topic", "era")},
                 "images": [{"id": r["id"], "commons_title": r["title"], "commons_description": r["description"][:200]} for r in batch]},
                [r["preview"] for r in batch])
            items = result.get("images")
            by_id = {i.get("id"): i for i in items if isinstance(i, dict)} if isinstance(items, list) else {}
            for r in batch:
                item = by_id.get(r["id"])
                if item is None and isinstance(items, list) and len(items) == len(batch):
                    item = items[batch.index(r)]
                r["tags"] = self._clean_tags(item)
        save(self.out / "image_tags.json", {r["id"]: {**r["tags"], "title": r["title"], "license": r["license"]} for r in self.records if "tags" in r})
        self.report()

    @staticmethod
    def _clean_tags(item):
        if not isinstance(item, dict):
            return {"usable": False, "reason": "no assessment"}
        def number(key):
            v = item.get(key)
            return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= 1 else None
        relevance, impact = number("relevance"), number("impact")
        depicts = item.get("depicts")
        if relevance is None or impact is None or not isinstance(depicts, str) or not depicts.strip():
            return {"usable": False, "reason": "invalid assessment"}
        graphic, overlay = item.get("graphic") is not False, item.get("modern_overlay") is not False
        return {"usable": not graphic and not overlay and relevance >= 0.5, "relevance": relevance, "impact": impact,
                "depicts": depicts.strip()[:240], "kind": str(item.get("kind", "other"))[:20], "graphic": graphic, "modern_overlay": overlay}

    @property
    def usable(self):
        return [r for r in self.records if r.get("tags", {}).get("usable")]


# ---------------------------------------------------------------- assignment & timeline

def assign_images(model, plan, scenes, pool, out):
    """Ask for a fitting image per scene using only vision-derived tags, then validate."""
    usable = pool.usable
    if len(usable) < 8:
        raise Blocked("VISUALS_INSUFFICIENT", f"Only {len(usable)} licensed, relevant, non-graphic images were found (need at least 8). "
                      "Inspect image_sources.json and image_tags.json; no unrelated stand-ins are used.")
    by_id = {r["id"]: r for r in usable}
    candidates = [{"id": r["id"], "depicts": r["tags"]["depicts"], "kind": r["tags"]["kind"], "relevance": r["tags"]["relevance"]} for r in usable]
    chosen = {}
    for start in range(0, len(scenes), 8):
        batch = scenes[start:start + 8]
        result = model.json(
            'Choose images for each narrated scene of a history video from the candidate list only. Return {"scenes":[{"id":int,'
            '"images":[{"id":str,"fit":"direct|context","confidence":0..1}]}]} with 1-4 images per scene, best first. '
            '"direct" = the image visibly shows what the narration is about. "context" = same period/place/theme but not the exact moment. '
            'NEVER present an image of a different person, event, place or era as a specific named person or event. '
            'Prefer varied images across neighbouring scenes. Only use the candidate descriptions; do not invent content.',
            {"topic": plan.get("english_topic"), "scenes": [{"id": s["id"], "narration": s["narration"], "visual_need": s["visual_need"]} for s in batch],
             "candidates": candidates})
        entries = result.get("scenes")
        if not isinstance(entries, list):
            raise Blocked("MODEL_SCHEMA", "Assignment response has no scenes list")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("images"), list):
                continue
            picks = []
            for i in entry["images"]:
                if not isinstance(i, dict) or i.get("id") not in by_id or i.get("fit") not in {"direct", "context"}:
                    continue
                conf = i.get("confidence")
                if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not math.isfinite(conf):
                    continue
                if conf >= (0.6 if i["fit"] == "direct" else 0.5):
                    picks.append({"id": i["id"], "fit": i["fit"], "confidence": float(conf)})
            chosen[entry.get("id")] = picks
    save(Path(out) / "image_assignments.json", chosen)
    return chosen


MOTIONS = ("zoom_in", "pan_right", "zoom_out", "pan_left")


def build_timeline(scenes, seconds, chosen, pool, *, shot_target=6.5, max_reuse=3):
    """Return one shot list per scene whose lengths add up exactly to the narration length."""
    usable = {r["id"]: r for r in pool.usable}
    # Topic-level fillers: most relevant images first, used only when a scene lacks its own matches.
    filler = sorted(usable.values(), key=lambda r: (-r["tags"]["relevance"], -r["tags"]["impact"]))
    filler = [r for r in filler if r["tags"]["relevance"] >= 0.7] or filler
    uses = {}
    timeline, previous = [], None
    for index, (scene, length) in enumerate(zip(scenes, seconds, strict=True)):
        count = max(1, round(length / shot_target))
        picks = [p["id"] for p in chosen.get(scene["id"], []) if p["id"] in usable][:count]
        for r in filler:
            if len(picks) >= count:
                break
            if r["id"] not in picks and uses.get(r["id"], 0) < max_reuse and r["id"] != previous:
                picks.append(r["id"])
        if len(picks) < count:
            # Last resort: repeat this scene's own images at different framing rather than any unrelated picture.
            base = picks or [filler[0]["id"]]
            picks = [base[i % len(base)] for i in range(count)]
        shots = []
        each = length / count
        for j, image_id in enumerate(picks):
            uses[image_id] = uses.get(image_id, 0) + 1
            shots.append({"asset_id": image_id, "path": usable[image_id]["path"], "seconds": each,
                          "motion": MOTIONS[(index + j) % len(MOTIONS)]})
        previous = picks[-1]
        timeline.append(shots)
    return timeline


def chip_for(scene, claims_by_id):
    dates = sorted(str(claims_by_id[c]["date"]) for c in scene.get("claim_ids", []) if c in claims_by_id and claims_by_id[c].get("date"))
    if not dates:
        return ""
    m = re.fullmatch(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", dates[0])
    if not m:
        return ""
    text = f"{int(m[1])}年"
    if m[2]:
        text += f"{int(m[2])}月"
    if m[3]:
        text += f"{int(m[3])}日"
    return text


# ---------------------------------------------------------------- hook audit & packaging

def audit_hook(model, scenes, ledger):
    claims = [c for c in ledger["claims"] if c["id"] in {cid for s in scenes[:4] for cid in s["claim_ids"]}]
    audit = model.json(
        'Audit the first four narrated scenes of a history video as an opening hook. Return {"opens_with_outcome_or_paradox":bool,'
        '"has_open_question":bool,"no_greeting_or_preamble":bool,"supported_by_claims":bool,"reason":str}. '
        'A good hook states the most surprising supported outcome or contradiction in the first sentences and raises a question the video answers. '
        'Be strict: a calendar date, a definition or a greeting as the opening line is a failure.',
        {"scenes": [s["narration"] for s in scenes[:4]], "claims": claims})
    keys = ("opens_with_outcome_or_paradox", "has_open_question", "no_greeting_or_preamble", "supported_by_claims")
    audit["passed"] = all(audit.get(k) is True for k in keys)
    return audit


def packaging(model, plan, ledger, script):
    """Honest title, thumbnail text, description and tags. Falls back to deterministic values."""
    topic = plan.get("original_topic", "")
    fallback = {"title": topic[:60] or script["title"][:60], "thumbnail_text": re.sub(r"\s+", "", topic)[:10] or "歷史",
                "intro": script["scenes"][0]["narration"], "tags": [t for t in ("歷史", "冷知識", "歷史故事", topic[:20]) if t]}
    try:
        draft = model.json(
            'Write packaging for a Traditional Chinese history video. Return {"title":str (<=36 chars, curiosity-driven but strictly true),'
            '"thumbnail_text":str (<=10 Chinese chars, punchy, no punctuation),"intro":str (2-3 sentences, no spoilers of the final answer),'
            '"tags":[8-12 short Traditional Chinese or English tags]}. Every factual implication must be supported by the supplied claims. '
            'No false promises, no all-caps hype, no misleading comparisons.',
            {"topic": plan.get("original_topic"), "claims": [c["statement"] for c in ledger["claims"]][:20], "first_scenes": [s["narration"] for s in script["scenes"][:4]]})
        title, thumb, intro, tags = draft.get("title"), draft.get("thumbnail_text"), draft.get("intro"), draft.get("tags")
        ok = (isinstance(title, str) and 4 <= len(title.strip()) <= 40 and isinstance(thumb, str) and 2 <= len(thumb.strip()) <= 12
              and isinstance(intro, str) and 10 <= len(intro) <= 400 and isinstance(tags, list) and 3 <= len(tags) <= 15
              and all(isinstance(t, str) and 0 < len(t) <= 30 for t in tags))
        if ok:
            check = model.json('Return {"supported":bool,"misleading":bool,"reason":str}. supported = every implied fact in the title, thumbnail text and intro is in the claims; '
                               'misleading = the packaging promises something the video does not deliver.',
                               {"title": title, "thumbnail_text": thumb, "intro": intro, "claims": [c["statement"] for c in ledger["claims"]]})
            if check.get("supported") is True and check.get("misleading") is False:
                return {"title": title.strip(), "thumbnail_text": thumb.strip(), "intro": intro.strip(), "tags": [t.strip() for t in tags], "source": "model_audited"}
    except Blocked:
        pass
    return {**fallback, "source": "fallback"}


def stamp_minutes(seconds):
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


def description_text(pack, chapters, sources, images, music):
    lines = [pack["intro"], "", "章節"]
    lines += [f"{stamp_minutes(start)} {name}" for start, name in chapters]
    lines += ["", DISCLOSURE, "", "資料來源"]
    lines += [f"- {s.get('title', '')[:80]} {s.get('url', '')}".strip() for s in sources[:12]]
    by = [r for r in images if r["license_kind"] == "by"]
    pd = [r for r in images if r["license_kind"] == "pd"]
    lines += ["", f"圖片來源：Wikimedia Commons（公有領域 {len(pd)} 張、CC BY {len(by)} 張）。CC BY 圖片如下："]
    lines += [f"- {r['title'].removeprefix('File:')} — {r['creator'][:80]}，{r['license']}，{r['source_url']}" for r in by]
    if music:
        lines += ["", f"音樂：{music['title'].removeprefix('File:')} — {music['creator'][:80]}，{music['license']}，{music['source_url']}"]
    return "\n".join(lines)[:4900]


# ---------------------------------------------------------------- music

MUSIC_QUERIES = ["instrumental ambient music", "cinematic orchestral instrumental", "dramatic suspense instrumental music"]
_MUSIC_GOOD = re.compile(r"music|instrumental|ambient|orchestra|piano|symphon|theme|composition|soundtrack|suite|sonata", re.I)
_MUSIC_BAD = re.compile(r"speech|spoken|interview|bird|sound effect|voice|reading|news|radio|podcast|lecture|song of|sermon|anthem", re.I)


def pick_music(web, out, *, delay=0.25):
    """One licensed instrumental track, or None. Music is optional and never blocks a video."""
    out = Path(out)
    for q in MUSIC_QUERIES:
        try:
            data = web.json(COMMONS, {"action": "query", "format": "json", "generator": "search", "gsrsearch": q + " filetype:audio",
                                      "gsrnamespace": 6, "gsrlimit": 12, "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata"})
            for page in data.get("query", {}).get("pages", {}).values():
                info = (page.get("imageinfo") or [{}])[0]
                if not str(info.get("mime", "")).startswith(("audio/", "application/ogg")):
                    continue
                probe_page = {**page, "imageinfo": [{**info, "mime": "image/jpeg", "width": 2000, "height": 2000}]}
                record = licensed_media_record(probe_page, max_bytes=45_000_000)
                text = record and (record["title"] + " " + record["categories"] + " " + record["description"])
                if not record or not _MUSIC_GOOD.search(text) or _MUSIC_BAD.search(text):
                    continue
                record["url"] = info.get("url", "")
                raw, _ = web.get(record["url"], limit=45_000_000)
                suffix = Path(record["url"]).suffix.lower() or ".ogg"
                path = out / ("music" + suffix)
                path.write_bytes(raw)
                record.update({"path": str(path), "mime": info.get("mime")})
                return record
        except (Blocked, ValueError, AttributeError, TypeError, OSError):
            continue
        finally:
            if delay:
                time.sleep(delay)
    return None
