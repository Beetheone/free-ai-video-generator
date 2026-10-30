"""Optional private YouTube upload through the Data API (resumable). Secrets come from the environment only.

Required environment: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (OAuth, scope youtube.upload).
Videos are always uploaded as PRIVATE with the altered/synthetic content disclosure on; you publish after review.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
THUMB_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
CHUNK = 8 * 1024 * 1024


class UploadError(RuntimeError):
    pass


def access_token(session=requests):
    env = {k: os.getenv(k, "") for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")}
    missing = [k for k, v in env.items() if not v]
    if missing:
        raise UploadError("Missing secrets: " + ", ".join(missing))
    r = session.post(TOKEN_URL, data={"client_id": env["YT_CLIENT_ID"], "client_secret": env["YT_CLIENT_SECRET"],
                                      "refresh_token": env["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}, timeout=30)
    if r.status_code != 200 or "access_token" not in r.json():
        raise UploadError(f"OAuth refresh failed (HTTP {r.status_code})")
    return r.json()["access_token"]


def metadata(title, description, tags):
    return {"snippet": {"title": title[:100], "description": description[:4900], "tags": [t for t in tags if t][:15],
                        "categoryId": "27", "defaultLanguage": "zh-TW", "defaultAudioLanguage": "zh-TW"},
            "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}}


def upload(video, title, description, tags, thumbnail=None, session=requests):
    video = Path(video)
    token = access_token(session)
    auth = {"Authorization": "Bearer " + token}
    size = video.stat().st_size
    start = session.post(UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"},
                         headers={**auth, "Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Type": "video/mp4",
                                  "X-Upload-Content-Length": str(size)},
                         data=json.dumps(metadata(title, description, tags)), timeout=60)
    if start.status_code != 200 or not start.headers.get("Location"):
        raise UploadError(f"Upload session refused (HTTP {start.status_code})")
    location, offset, result = start.headers["Location"], 0, None
    with video.open("rb") as f:
        while offset < size:
            chunk = f.read(CHUNK)
            end = offset + len(chunk) - 1
            r = session.put(location, data=chunk, headers={**auth, "Content-Length": str(len(chunk)),
                            "Content-Range": f"bytes {offset}-{end}/{size}", "Content-Type": "video/mp4"}, timeout=300)
            if r.status_code in (200, 201):
                result = r.json()
                break
            if r.status_code != 308:
                raise UploadError(f"Chunk upload failed (HTTP {r.status_code})")
            offset = end + 1
    if not result or "id" not in result:
        raise UploadError("Upload finished without a video id")
    outcome = {"video_id": result["id"], "privacy": "private", "studio_url": "https://studio.youtube.com/video/" + result["id"] + "/edit",
               "thumbnail": "skipped"}
    if thumbnail and Path(thumbnail).is_file():
        t = session.post(THUMB_URL, params={"videoId": result["id"], "uploadType": "media"},
                         headers={**auth, "Content-Type": "image/jpeg"}, data=Path(thumbnail).read_bytes(), timeout=60)
        # Custom thumbnails need a phone-verified channel; the video itself is already safely uploaded.
        outcome["thumbnail"] = "set" if t.status_code == 200 else f"not set (HTTP {t.status_code})"
    return outcome


def main(argv=None):
    p = argparse.ArgumentParser(description="Upload a finished history video as PRIVATE for review")
    p.add_argument("--dir", type=Path, required=True, help="a run directory containing documentary.mp4, packaging.json, DESCRIPTION.txt")
    args = p.parse_args(argv)
    try:
        pack = json.loads((args.dir / "packaging.json").read_text("utf-8"))
        outcome = upload(args.dir / "documentary.mp4", pack["title"], (args.dir / "DESCRIPTION.txt").read_text("utf-8"),
                         pack["tags"], args.dir / "thumbnail.jpg")
    except (UploadError, OSError, ValueError, KeyError, requests.RequestException) as exc:
        print(f"::error title=YouTube upload failed::{type(exc).__name__}: {str(exc)[:160]}")
        return 2
    (args.dir / "youtube_upload.json").write_text(json.dumps(outcome, ensure_ascii=False, indent=2), encoding="utf-8")
    print("::notice title=YouTube::uploaded privately, video id " + outcome["video_id"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
