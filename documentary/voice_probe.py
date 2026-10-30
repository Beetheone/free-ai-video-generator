"""Tiny reachability probe for the free Edge voice. Prints only an error type and HTTP status, never URLs or tokens."""
import asyncio
import os
import re
import sys


async def _stream(voice):
    import edge_tts
    got = False
    async for msg in edge_tts.Communicate("測試", voice=voice, proxy=os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")).stream():
        got = got or msg["type"] == "audio"
    return got


def probe(voice="zh-TW-YunJheNeural", timeout=40):
    """Return (ok, detail). Never raises."""
    try:
        return bool(asyncio.run(asyncio.wait_for(_stream(voice), timeout))), "audio received"
    except Exception as exc:
        status = re.search(r"\b(4\d\d|5\d\d)\b", str(exc))
        return False, type(exc).__name__ + (f" HTTP {status[1]}" if status else "")


def main():
    ok, detail = probe()
    print(f"::notice title=Edge voice::{'reachable' if ok else 'unavailable'} ({detail})")
    path = os.getenv("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write("ok=" + str(ok).lower() + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
