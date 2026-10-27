"""Pixabay video API integration: bounded searches, no mass downloads.
API responses cached on disk for 24 hours; keep cache via GitHub Actions cache.
"""
import json,os,time,hashlib,requests
from pathlib import Path
API="https://pixabay.com/api/videos/"
CACHE=Path(".pixabay_cache")
def query_results(term,key):
    CACHE.mkdir(exist_ok=True)
    tag=hashlib.sha256(term.lower().encode()).hexdigest()[:16]
    cache=CACHE/f"{tag}.json"
    if cache.exists() and time.time()-cache.stat().st_mtime<86400:
        return json.loads(cache.read_text("utf-8"))
    r=requests.get(API,params={"key":key,"q":term[:100],"per_page":3,"safesearch":"true","video_type":"film"},timeout=18)
    r.raise_for_status()
    data=r.json()
    cache.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
    return data
def fetch_pixabay_video(query,dest,credits,scene):
    key=os.getenv("PIXABAY_API_KEY","").strip()
    if not key:return False
    # API use must be proportionate, not bulk harvesting. At most 8 distinct queries.
    seen_file=CACHE/"query_budget.json"
    CACHE.mkdir(exist_ok=True)
    seen=json.loads(seen_file.read_text("utf-8")) if seen_file.exists() else []
    q=" ".join(query.split()[:3]).strip()
    if q not in seen and len(seen)>=8:
        print("Pixabay daily query budget reached; falling back",flush=True)
        return False
    if q not in seen:
        seen.append(q);seen_file.write_text(json.dumps(seen),encoding="utf-8")
    try:
        data=query_results(q,key)
        for item in data.get("hits",[])[:2]:
            rend=item.get("videos",{}).get("medium",{})
            url=rend.get("url")
            if not url or rend.get("size",0)>30_000_000:continue
            with requests.get(url,stream=True,timeout=35) as r:
                r.raise_for_status()
                with open(dest,"wb") as f:
                    total=0
                    for chunk in r.iter_content(262144):
                        total+=len(chunk)
                        if total>32_000_000:raise RuntimeError("Video exceeds budget")
                        f.write(chunk)
            if Path(dest).stat().st_size < 100_000: continue
            credits.append({"scene":scene,"type":"video","provider":"Pixabay","source":item.get("pageURL"),"creator":item.get("user"),"license":"Pixabay Content License","tags":item.get("tags")})
            print("Pixabay video scene",scene,item.get("id"),flush=True)
            return True
    except Exception as e:
        print("Pixabay unavailable:",str(e)[:180],flush=True)
    return False
