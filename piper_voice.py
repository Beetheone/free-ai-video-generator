"""Offline Chinese speech synthesis on GitHub Actions via Piper."""
from pathlib import Path
import subprocess
from opencc import OpenCC

VOICE = "zh_CN-huayan-medium"
CONVERTER = OpenCC("t2s")

def synthesize(text, output_file):
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    simplified = CONVERTER.convert(text)
    proc = subprocess.run(
        ["piper", "--model", VOICE, "--output_file", str(output_file)],
        input=simplified, text=True, capture_output=True, timeout=240,
    )
    if proc.returncode != 0 or not output_file.is_file() or output_file.stat().st_size < 1000:
        raise RuntimeError("Piper TTS failed: " + (proc.stderr or proc.stdout)[-2500:])
    return output_file
