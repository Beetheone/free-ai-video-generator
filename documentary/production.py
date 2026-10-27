"""Real narration, measured subtitles, bounded CPU FFmpeg editing and output QA."""
import asyncio
import math
import os
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .core import Blocked, command, duration, probe, save

FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"


def caption_chunks(text, limit=24):
    parts = []
    for phrase in re.findall(r"[^。！？；，、,.!?;]+[。！？；，、,.!?;]?", text):
        parts.extend(phrase[i:i+limit] for i in range(0, len(phrase), limit))
    return [p.strip() for p in parts if p.strip()]


def validate_cues(cues, seconds):
    last = 0
    if not cues:
        raise Blocked("CAPTIONS_MISSING", "No timed captions generated")
    for cue in cues:
        a, b, text = cue["start"], cue["end"], cue["text"]
        if not (math.isfinite(a) and math.isfinite(b) and 0 <= a < b <= seconds+0.1) or a < last-0.01:
            raise Blocked("CAPTION_TIMING", "Caption overlap or timestamp outside narration")
        if not text.strip() or len(text) > 48 or b-a > 8.5 or len(text)/(b-a) > 16:
            raise Blocked("CAPTION_READABILITY", "Caption too long, too fast, or too short to read")
        last = b


async def edge_voice(text, path, voice):
    import edge_tts
    words = []
    # edge-tts does not automatically inherit HTTPS_PROXY for its websocket transport.
    tts = edge_tts.Communicate(text, voice=voice, boundary="WordBoundary",
                              proxy=os.getenv("HTTPS_PROXY") or os.getenv("https_proxy"))
    try:
        with path.open("wb") as f:
            async for msg in tts.stream():
                if msg["type"] == "audio":
                    f.write(msg["data"])
                elif msg["type"] == "WordBoundary":
                    words.append({"start": msg["offset"]/10_000_000,
                                  "end": (msg["offset"]+msg["duration"])/10_000_000, "text": msg["text"]})
    except Exception as exc:
        raise Blocked("TTS_UNAVAILABLE", f"Edge TTS failed ({type(exc).__name__}); select Kokoro CPU with its optional dependencies/model") from None
    if not words:
        raise Blocked("CAPTIONS_MISSING", "TTS returned no word timestamps")
    cues, group = [], []
    for word in words:
        if group and (len("".join(w["text"] for w in group))+len(word["text"]) > 24 or word["end"]-group[0]["start"] > 7):
            cues.append({"start": group[0]["start"], "end": group[-1]["end"], "text": "".join(w["text"] for w in group)})
            group = []
        group.append(word)
    if group:
        cues.append({"start": group[0]["start"], "end": group[-1]["end"], "text": "".join(w["text"] for w in group)})
    # Preserve Traditional Chinese input in captions. Only punctuation may differ in word events.
    normalized = lambda s: re.sub(r"[\W_]", "", s)
    if normalized("".join(c["text"] for c in cues)) != normalized(text):
        raise Blocked("CAPTION_TEXT_MISMATCH", "Word events do not reproduce narration text")
    return cues


def synthesize(text, dest, engine="edge", voice="zh-TW-YunJheNeural"):
    if engine == "edge":
        cues = asyncio.run(edge_voice(text, dest, voice))
    elif engine == "kokoro":
        try:
            from kokoro_voice import synthesize as kokoro
        except ImportError:
            raise Blocked("KOKORO_DEPENDENCY", "Install kokoro, misaki[zh], soundfile and espeak-ng; see documentary guide") from None
        cues, offset, parts = [], 0.0, []
        # Measured phrase boundaries, explicitly NOT fabricated word alignment.
        for i, phrase in enumerate(caption_chunks(text)):
            path = dest.with_name(f"{dest.stem}-phrase-{i}.wav")
            kokoro(phrase, path)
            seconds = duration(path)
            cues.append({"start": offset, "end": offset+seconds, "text": phrase})
            offset += seconds
            parts.append(path)
        concat_audio(parts, dest)
    else:
        raise Blocked("TTS_ENGINE", f"Unsupported voice engine: {engine}")
    seconds = duration(dest)
    validate_cues(cues, seconds)
    return {"path": str(dest), "seconds": seconds, "cues": cues,
            "timing_method": "provider_word_events" if engine == "edge" else "measured_phrase_audio"}


def concat_audio(paths, dest):
    # Absolute paths are written by us, never interpreted by a shell.
    manifest = dest.with_suffix(".concat.txt")
    manifest.write_text("".join("file '" + str(Path(p).resolve()).replace("'", "'\\''") + "'\n" for p in paths))
    command(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", manifest, "-ar", "24000", "-ac", "1", dest])


def stamp(seconds, ass=False):
    units = round(seconds*(100 if ass else 1000))
    scale = 100 if ass else 1000
    hours, rem = divmod(units, 3600*scale)
    minutes, rem = divmod(rem, 60*scale)
    secs, fraction = divmod(rem, scale)
    return f"{hours}:{minutes:02}:{secs:02}.{fraction:02}" if ass else f"{hours:02}:{minutes:02}:{secs:02},{fraction:03}"


def safe_text(text):
    return text.replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\n", " ").replace("\r", " ")


def ass_file(path, cues, seconds, info):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Noto Sans CJK TC,48,&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,0,0,0,0,100,100,0,0,1,3,1,2,100,100,65,1
Style: Info,Noto Sans CJK TC,30,&H00FFFFFF,&H00FFFFFF,&H00302010,&H90000000,0,0,0,0,100,100,0,0,3,10,0,7,65,65,55,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    rows = []
    for c in cues:
        text = safe_text(c["text"])
        if len(text) > 24:
            text = text[:24] + r"\N" + text[24:]
        rows.append(f"Dialogue: 1,{stamp(c['start'],True)},{stamp(c['end'],True)},Caption,,0,0,0,,{text}")
    rows.append(f"Dialogue: 0,0:00:00.00,{stamp(min(seconds,3),True)},Info,,0,0,0,,{{\\fad(200,200)}}{safe_text(info)}")
    path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")


def render_scene(scene, audio, shots, work):
    if not shots or sum(s["end"]-s["start"] for s in shots) < audio["seconds"]-0.02:
        raise Blocked("FOOTAGE_COVERAGE", "Cannot render scene without full real footage coverage")
    args = ["ffmpeg", "-v", "error", "-y", "-threads", "2"]
    for shot in shots:
        args += ["-ss", shot["start"], "-t", shot["end"]-shot["start"], "-i", shot["path"]]
    args += ["-i", audio["path"]]
    ass = work / f"captions-{scene['id']}.ass"
    ass_file(ass, audio["cues"], audio["seconds"], scene["info"])
    # Escape ffmpeg filter syntax even when output directory contains apostrophes or colons.
    escaped = str(ass.resolve()).replace("\\", "\\\\").replace(":", "\\:").replace("'", "'\\''")
    filters = []
    for i in range(len(shots)):
        filters.append(f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24,setpts=PTS-STARTPTS,format=yuv420p[v{i}]")
    filters.append("".join(f"[v{i}]" for i in range(len(shots))) + f"concat=n={len(shots)}:v=1:a=0,ass=filename='{escaped}'[v]")
    out = work / f"scene-{scene['id']}.mp4"
    args += ["-filter_complex_threads", "2", "-filter_complex", ";".join(filters),
             "-map", "[v]", "-map", f"{len(shots)}:a:0", "-t", audio["seconds"],
             "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:v", "libx264", "-threads", "2", "-preset", "veryfast",
             "-crf", "22", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out]
    command(args, timeout=900)
    return out


def render(script, narration, timeline, out):
    work = out / "work"
    work.mkdir(exist_ok=True)
    parts, cues, offset = [], [], 0.0
    for scene, audio, shots in zip(script["scenes"], narration, timeline, strict=True):
        parts.append(render_scene(scene, audio, shots, work))
        for cue in audio["cues"]:
            cues.append({**cue, "start": offset+cue["start"], "end": offset+cue["end"]})
        offset += audio["seconds"]
    validate_cues(cues, offset)
    (out / "documentary.srt").write_text("\n".join(f"{i}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}\n" for i,c in enumerate(cues,1)), encoding="utf-8")
    manifest = work / "video.concat.txt"
    manifest.write_text("".join("file '"+str(p.resolve()).replace("'", "'\\''")+"'\n" for p in parts))
    candidate = out / "candidate.mp4"
    command(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", manifest, "-c", "copy", "-movflags", "+faststart", candidate], timeout=300)
    return candidate, cues


def inspect_media(path, expected_seconds, cues, min_seconds=600, max_seconds=900):
    media = probe(path)
    seconds = float(media["format"]["duration"])
    video = next((x for x in media["streams"] if x["codec_type"] == "video"), {})
    audio = next((x for x in media["streams"] if x["codec_type"] == "audio"), {})
    failures = []
    if video.get("width") != 1920 or video.get("height") != 1080 or video.get("codec_name") != "h264" or audio.get("codec_name") != "aac":
        failures.append("Output must contain 1080p H.264 video and AAC narration")
    if not min_seconds <= seconds <= max_seconds or abs(seconds-expected_seconds) > 1:
        failures.append("Measured runtime outside requested range or A/V duration drift")
    try:
        validate_cues(cues, seconds)
    except Blocked as exc:
        failures.append(str(exc))
    # Decode the actual output, detect long blank/frozen video and missing/silent narration.
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-threads", "2", "-i", str(path),
        "-vf", "scale=480:-2,blackdetect=d=1.5:pix_th=0.1,freezedetect=n=-50dB:d=12",
        "-af", "silencedetect=noise=-45dB:d=3,volumedetect", "-f", "null", "-"], capture_output=True, text=True, timeout=1800)
    if p.returncode:
        failures.append("Output failed full decode")
    if "black_start:" in p.stderr:
        failures.append("Long black interval detected")
    if "freeze_start:" in p.stderr:
        failures.append("Frozen video interval detected")
    if "silence_start:" in p.stderr:
        failures.append("Narration silence exceeds three seconds")
    peak = re.search(r"max_volume: ([-\w.]+) dB", p.stderr)
    if not peak or float(peak[1]) < -35:
        failures.append("Narration peak missing or inaudible")
    return {"passed": not failures, "failures": failures, "seconds": seconds,
            "expected_seconds": expected_seconds, "caption_cues": len(cues), "full_decode": p.returncode == 0,
            "scope": "technical checks and prior automated evidence/visual gates; not a human editorial or legal review"}


def thumbnail(candidate, title, dest):
    if not Path(FONT).is_file():
        raise Blocked("CJK_FONT_MISSING", "Install fonts-noto-cjk for readable Traditional Chinese titles")
    command(["ffmpeg", "-v", "error", "-y", "-ss", "1", "-i", candidate, "-frames:v", "1", dest])
    im = Image.open(dest).convert("RGB").resize((1280,720))
    panel = Image.new("RGBA", im.size, (0,0,0,0))
    draw = ImageDraw.Draw(panel)
    draw.rectangle((0,470,1280,720), fill=(0,0,0,200))
    font = ImageFont.truetype(FONT, 52, index=3)  # TTC Traditional Chinese face
    text = safe_text(title[:42])
    draw.multiline_text((48,500), "\n".join(text[i:i+21] for i in range(0,len(text),21)), font=font, fill="white", stroke_width=2, stroke_fill="black", spacing=12)
    Image.alpha_composite(im.convert("RGBA"),panel).convert("RGB").save(dest)
