"""Ken Burns motion over licensed archive images, burnt captions, music ducking and thumbnails."""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .core import Blocked, command, duration
from .production import FONT, ass_file, concat_audio, safe_text, stamp, validate_cues

FPS = 24
CANVAS = (3840, 2160)  # 2x the output so the slow zoom does not stair-step


def zoompan(motion, frames):
    n = max(frames, 1)
    if motion == "zoom_out":
        return f"z='1.18-0.18*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    if motion == "pan_right":
        return f"z='1.14':x='(iw-iw/zoom)*on/{n}':y='ih/2-(ih/zoom/2)'"
    if motion == "pan_left":
        return f"z='1.14':x='(iw-iw/zoom)*(1-on/{n})':y='ih/2-(ih/zoom/2)'"
    return f"z='1+0.18*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"


def split_frames(seconds_list, total_seconds):
    """Integer frame counts per shot that always cover the whole narration."""
    total = math.ceil(total_seconds * FPS) + 1
    weights = [s / sum(seconds_list) for s in seconds_list]
    frames = [max(int(total * w), 1) for w in weights]
    frames[-1] += total - sum(frames)
    return frames


def render_scene(scene, audio, shots, work, chip):
    if not shots or any(not Path(s["path"]).is_file() for s in shots):
        raise Blocked("VISUALS_MISSING", f"Scene {scene['id']} has no usable image file")
    frames = split_frames([s["seconds"] for s in shots], audio["seconds"])
    args = ["ffmpeg", "-v", "error", "-y", "-threads", "2"]
    for shot in shots:
        args += ["-i", shot["path"]]
    w, h = CANVAS
    parts = []
    for i, (shot, n) in enumerate(zip(shots, frames)):
        # Blurred cover layer + fitted original: portraits and odd ratios never get cropped or stretched.
        parts.append(f"[{i}:v]format=rgb24,split=2[bg{i}][fg{i}];"
                     f"[bg{i}]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=60:8[bb{i}];"
                     f"[fg{i}]scale={w}:{h}:force_original_aspect_ratio=decrease[fs{i}];"
                     f"[bb{i}][fs{i}]overlay=(W-w)/2:(H-h)/2,setsar=1,"
                     f"zoompan={zoompan(shot['motion'], n)}:d={n}:s=1920x1080:fps={FPS},format=yuv420p,setpts=PTS-STARTPTS[v{i}]")
    ass = work / f"captions-{scene['id']}.ass"
    ass_file(ass, audio["cues"], audio["seconds"], chip)
    escaped = str(ass.resolve()).replace("\\", "\\\\").replace(":", "\\:").replace("'", "'\\''")
    graph = ";".join(parts) + ";" + "".join(f"[v{i}]" for i in range(len(shots))) + f"concat=n={len(shots)}:v=1:a=0,ass=filename='{escaped}'[v]"
    out = work / f"scene-{scene['id']}.mp4"
    args += ["-filter_complex_threads", "2", "-filter_complex", graph, "-map", "[v]", "-an", "-t", audio["seconds"],
             "-c:v", "libx264", "-threads", "2", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    command(args, timeout=900)
    return out


def render(script, narration, timeline, chips, out, music_path=None):
    work = out / "work"
    work.mkdir(exist_ok=True)
    parts, cues, offset = [], [], 0.0
    for scene, audio, shots, chip in zip(script["scenes"], narration, timeline, chips, strict=True):
        parts.append(render_scene(scene, audio, shots, work, chip))
        for cue in audio["cues"]:
            cues.append({**cue, "start": offset + cue["start"], "end": offset + cue["end"]})
        offset += audio["seconds"]
    validate_cues(cues, offset)
    (out / "documentary.srt").write_text("\n".join(f"{i}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}\n" for i, c in enumerate(cues, 1)), encoding="utf-8")
    manifest = work / "video.concat.txt"
    manifest.write_text("".join("file '" + str(p.resolve()).replace("'", "'\\''") + f"'\nduration {a['seconds']:.9f}\n" for p, a in zip(parts, narration, strict=True)))
    voice = work / "narration.wav"
    concat_audio([a["path"] for a in narration], voice)
    if abs(duration(voice) - offset) > 0.01:
        raise Blocked("NARRATION_TIMING", "Decoded narration differs from measured scene timeline; no video is released")
    candidate = out / "candidate.mp4"
    args = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", manifest, "-i", voice]
    if music_path:
        # Quiet bed that dips whenever the narrator speaks; encoded once with the voice.
        args += ["-stream_loop", "-1", "-i", music_path]
        graph = ("[1:a]aformat=sample_rates=48000:channel_layouts=mono,asplit=2[v1][v2];"
                 "[2:a]aformat=sample_rates=48000:channel_layouts=mono,volume=0.28[m];"
                 "[m][v2]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=600[md];"
                 "[v1][md]amix=inputs=2:duration=first:weights='1 1':dropout_transition=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]")
        audio_args = ["-filter_complex", graph, "-map", "0:v:0", "-map", "[a]"]
    else:
        audio_args = ["-map", "0:v:0", "-map", "1:a:0", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11"]
    command(args + audio_args + ["-t", offset, "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-ac", "1", "-b:a", "160k",
                                 "-movflags", "+faststart", candidate], timeout=600)
    return candidate, cues


def history_thumbnail(image_path, text, dest):
    if not Path(FONT).is_file():
        raise Blocked("CJK_FONT_MISSING", "Install fonts-noto-cjk for readable Traditional Chinese titles")
    im = Image.open(image_path).convert("RGB")
    target = 1280 / 720
    if im.width / im.height > target:
        new_w = round(im.height * target)
        im = im.crop(((im.width - new_w) // 2, 0, (im.width + new_w) // 2, im.height))
    else:
        new_h = round(im.width / target)
        im = im.crop((0, max((im.height - new_h) // 3, 0), im.width, max((im.height - new_h) // 3, 0) + new_h))
    im = im.resize((1280, 720), Image.LANCZOS)
    # Left-to-right darkening keeps the subject visible and the text readable.
    shade = ImageOps.invert(Image.linear_gradient("L").rotate(90).resize(im.size)).point(lambda v: int(v * 190 / 255))
    im = Image.composite(Image.new("RGB", im.size, (0, 0, 0)), im, shade)
    clean = safe_text("".join(text.split()))[:12]
    lines = [clean[i:i + 6] for i in range(0, len(clean), 6)][:2]
    font = ImageFont.truetype(FONT, 150 if max(len(l) for l in lines) <= 6 else 120, index=3)
    draw = ImageDraw.Draw(im)
    y = 720 - 60 - len(lines) * 170
    for line in lines:
        draw.text((56, y), line, font=font, fill=(255, 214, 0), stroke_width=9, stroke_fill=(0, 0, 0))
        y += 170
    im.save(dest, "JPEG", quality=92)
