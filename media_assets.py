"""Download openly licensed imagery from Wikimedia Commons without an API key.
Each used item's attribution and license are written to output/media_credits.json.
"""
import html,json,re,requests
from pathlib import Path
from PIL import Image
from io import BytesIO
API="https://commons.wikimedia.org/w/api.php"
HEAD={"User-Agent":"DocumentaryBuilder/1.0 (Open educational documentary; github.com/Beetheone/free-ai-video-generator)"}
SEARCHES={
"charred ancient scroll":"Herculaneum papyri","ancient roman ruins":"Herculaneum ruins",
"ancient greek manuscript":"Herculaneum papyri","mount vesuvius volcano":"Mount Vesuvius",
"volcano eruption ash":"volcano eruption","roman villa architecture":"Villa of the Papyri",
"burnt paper closeup":"charred papyrus","dark ancient library":"ancient library",
"archaeological excavation":"archaeological excavation","fragile old parchment":"old manuscript",
"historical restoration tools":"manuscript conservation","computer tomography scanner":"computed tomography scanner",
"cabbage cross section":"cabbage cross section","x ray tomography machine":"computed tomography",
"abstract layered paper":"papyrus scroll","digital mesh wireframe":"3D mesh",
"black ink paper macro":"papyrus manuscript","grayscale digital texture":"X-ray tomography",
"machine learning visualization":"machine learning network","scientist computer lab":"research scientist computer",
"scientific collaboration laptops":"computer research laboratory","open source code screen":"programming computer screen",
"ancient greek lettering":"ancient Greek inscription","research breakthrough celebration":"scientific research",
"researchers working computers":"scientific computing","ancient greek philosophy statue":"Epicurus bust",
"food table ancient style":"Roman fresco food","museum visitors antiquity":"museum antiquities",
"rolled parchment layers":"papyrus scroll","computer processing data":"scientific computing",
"ancient scroll museum":"Herculaneum papyri","damaged manuscript fragment":"Herculaneum papyri",
"greek text columns":"ancient Greek papyrus","stoic philosopher statue":"Chrysippus statue",
"ancient marble sculpture":"Roman philosopher bust","historical manuscript reading":"ancient Greek manuscript",
"open access computer":"digital humanities research","research manuscript scholar":"classical manuscript scholar",
"artificial intelligence screen":"computer vision","data anomaly computer":"computer tomography",
"interdisciplinary scientists":"science laboratory","greek ancient alphabet":"ancient Greek inscription",
"ancient scroll collection":"Herculaneum papyri","ancient library reconstruction":"Library of Celsus",
"archaeologist museum archive":"museum archaeology","volcano sunset italy":"Mount Vesuvius",
"ancient parchment close up":"Herculaneum papyri","library books cinematic":"ancient library",
}
ALLOWED=("cc0","public domain","cc by","cc-by","cc-by-sa","cc by-sa")
def plain(t):return re.sub("<[^>]+>","",html.unescape(str(t or "")))
def try_image(query,dest,credits,scene_id):
    search=SEARCHES.get(query,query)
    try:
        p={"action":"query","format":"json","generator":"search","gsrsearch":f"filetype:bitmap {search}","gsrnamespace":6,"gsrlimit":12,"prop":"imageinfo","iiprop":"url|size|extmetadata","iiurlwidth":1600}
        r=requests.get(API,params=p,headers=HEAD,timeout=18);r.raise_for_status()
        pages=sorted(r.json().get("query",{}).get("pages",{}).values(),key=lambda x:x.get("index",99))
        for pg in pages:
            inf=(pg.get("imageinfo") or [{}])[0]; meta=inf.get("extmetadata") or {}
            lic=plain(meta.get("LicenseShortName",{}).get("value","")).lower()
            usage=plain(meta.get("UsageTerms",{}).get("value","")).lower()
            if not any(z in lic+" "+usage for z in ALLOWED):continue
            if inf.get("width",0)<800 or inf.get("height",0)<400:continue
            url=inf.get("thumburl") or inf.get("url")
            if not url:continue
            try:
                data=requests.get(url,headers=HEAD,timeout=30);data.raise_for_status()
                im=Image.open(BytesIO(data.content)).convert("RGB")
                if min(im.size)<400:continue
                im.save(dest,quality=88)
                credits.append({"scene":scene_id,"title":pg.get("title"),"source":inf.get("descriptionurl"),"license":lic,"creator":plain(meta.get("Artist",{}).get("value",""))[:300],"image_url":url})
                print("Wikimedia image:",scene_id,pg.get("title"),flush=True)
                return True
            except Exception as ex:print("Wikimedia file skipped",str(ex)[:110],flush=True)
    except Exception as ex:print("Wikimedia lookup failed:",str(ex)[:240],flush=True)
    return False
