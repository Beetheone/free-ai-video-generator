"""Licensed Wikimedia video fallback. Avoids YouTube scraping and records attribution."""
import requests,re,html
from pathlib import Path
API="https://commons.wikimedia.org/w/api.php"
HEAD={"User-Agent":"OpenDocumentaryMaker/1.1 (https://github.com/Beetheone/free-ai-video-generator)"}
SAFE=("public domain","cc0","cc by","cc-by")
def clean(x):return re.sub("<[^>]+>","",html.unescape(str(x or ""))).lower()
def fetch_video(query,out,credits,scene):
    candidates=[query,query.replace("cinematic","").strip(),"Mount Vesuvius","archaeological ruins"]
    for term in candidates[:2]:
        try:
            params={"action":"query","format":"json","generator":"search","gsrsearch":term+" filetype:video","gsrnamespace":6,"gsrlimit":12,"prop":"imageinfo","iiprop":"url|size|extmetadata"}
            result=requests.get(API,params=params,headers=HEAD,timeout=18)
            result.raise_for_status()
            for item in result.json().get("query",{}).get("pages",{}).values():
                inf=(item.get("imageinfo") or [{}])[0]
                meta=inf.get("extmetadata") or {}
                lic=clean(meta.get("LicenseShortName",{}).get("value",""))
                terms=clean(meta.get("UsageTerms",{}).get("value",""))
                if not any(z in lic+" "+terms for z in SAFE):continue
                url=inf.get("url","")
                if not url.lower().split("?")[0].endswith((".webm",".ogv",".mp4")):continue
                if inf.get("size",999999999)>60*1024*1024:continue
                resp=requests.get(url,stream=True,headers=HEAD,timeout=40)
                resp.raise_for_status()
                with open(out,"wb") as f:
                    total=0
                    for chunk in resp.iter_content(256*1024):
                        total+=len(chunk)
                        if total>65*1024*1024:raise ValueError("Video too large")
                        f.write(chunk)
                if Path(out).stat().st_size<100000:continue
                credits.append({"scene":scene,"type":"video","title":item.get("title"),"source":inf.get("descriptionurl"),"license":lic,"creator":clean(meta.get("Artist",{}).get("value",""))[:220]})
                return True
        except Exception as e:
            print("Commons video lookup issue:",str(e)[:160],flush=True)
    return False
