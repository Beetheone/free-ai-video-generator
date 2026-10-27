#!/usr/bin/env python3
"""Game documentary multi-agent MVP. Stdlib only; never invents footage or claims.
Outputs a research queue, storyboard, clip matches and blocking QA report.
"""
import argparse,csv,json,os,re,subprocess,sys,urllib.request,urllib.parse,xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"agent_output"
def save(name,data):
    OUT.mkdir(exist_ok=True)
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
def words(s):
    return set(re.findall(r"[a-zA-Z0-9]{2,}|[\u3400-\u9fff]{2,}",s.lower()))
def rss_research(topic,limit=12):
    # Headlines are leads, not verified facts. News RSS sources remain external.
    query=urllib.parse.quote(f'{topic} video game when:90d')
    url=f'https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en'
    records=[]
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"GameDocResearch/0.1"})
        with urllib.request.urlopen(req,timeout=18) as resp: root=ET.fromstring(resp.read(1_500_000))
        for node in root.findall(".//item")[:limit]:
            title=(node.findtext("title") or "").strip()
            link=(node.findtext("link") or "").strip()
            if title and link:records.append({"headline":title,"url":link,"published":node.findtext("pubDate"),"status":"unverified_lead"})
    except Exception as exc:
        print("Research RSS unavailable:",str(exc)[:200],flush=True)
    return records
def manifest_items(path):
    if not path.exists():return []
    data=json.loads(path.read_text("utf-8"))
    if not isinstance(data,list):raise ValueError("Asset manifest must be an array")
    return data
def probe(path):
    result=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)],capture_output=True,text=True,timeout=20)
    return float(result.stdout.strip()) if result.returncode==0 else 0
def validated_clips(items):
    clips=[];invalid=[]
    for i,item in enumerate(items):
        local=(ROOT/str(item.get("path",""))).resolve()
        # Never fetch YouTube URLs or unspecified files automatically.
        if not local.is_relative_to(ROOT) or not local.is_file() or local.suffix.lower() not in (".mp4",".mov",".mkv",".webm"):
            invalid.append({"entry":i,"reason":"local_video_missing_or_invalid"});continue
        if item.get("rights") not in ("own_recording","licensed","public_domain"):
            invalid.append({"entry":i,"reason":"usage_rights_not_confirmed"});continue
        if not item.get("source_url") and item.get("rights")!="own_recording":
            invalid.append({"entry":i,"reason":"source_url_missing"});continue
        try:duration=probe(local)
        except Exception:duration=0
        if duration<2:invalid.append({"entry":i,"reason":"ffprobe_failed_or_video_too_short"});continue
        clips.append({**item,"path":str(local.relative_to(ROOT)),"duration":duration})
    return clips,invalid
def scenes_from_file(path,topic):
    if not path.exists():return []
    data=json.loads(path.read_text("utf-8"))
    if not isinstance(data,list):raise ValueError("Scenes must be a JSON array")
    scenes=[]
    for i,x in enumerate(data,1):
        narration=str(x.get("narration","")).strip()
        if not narration:continue
        scenes.append({"scene":i,"narration":narration,"visual_need":x.get("visual") or x.get("stock_query") or topic,"source_verified":bool(x.get("source_verified",False)),"source_urls":x.get("source_urls",[])})
    return scenes
def choose(scenes,clips):
    used={};timeline=[]
    for s in scenes:
        target=words(s["visual_need"]+" "+s["narration"])
        ranked=[]
        for c in clips:
            desc=" ".join([str(c.get("game","")),str(c.get("event","")),str(c.get("description",""))," ".join(c.get("tags",[]))])
            overlap=len(words(desc)&target)
            score=overlap-0.8*used.get(c["path"],0)
            ranked.append((score,c))
        ranked.sort(key=lambda z:z[0],reverse=True)
        if not ranked or ranked[0][0]<=0:
            timeline.append({**s,"clip":None,"status":"missing_relevant_footage"});continue
        score,c=ranked[0];used[c["path"]]=used.get(c["path"],0)+1
        timeline.append({**s,"clip":{"path":c["path"],"source_url":c.get("source_url"),"rights":c["rights"],"match_score":round(score,2),"available_seconds":c["duration"]},"status":"matched_review_required"})
    return timeline
def main():
    a=argparse.ArgumentParser()
    a.add_argument("--topic",default="Pokémon Red Mew glitch")
    a.add_argument("--scenes",default="scenes.json")
    a.add_argument("--assets",default="game_assets/manifest.json")
    a.add_argument("--skip-rss",action="store_true")
    args=a.parse_args()
    leads=[] if args.skip_rss else rss_research(args.topic)
    scenes=scenes_from_file(ROOT/args.scenes,args.topic)
    clips,invalid=validated_clips(manifest_items(ROOT/args.assets))
    timeline=choose(scenes,clips)
    unmatched=sum(x["clip"] is None for x in timeline)
    report={"created_at":datetime.now(timezone.utc).isoformat(),"topic":args.topic,
        "research_leads":len(leads),"scenes":len(scenes),"validated_clips":len(clips),
        "invalid_clips":invalid,"scenes_missing_footage":unmatched,
        "verified_scene_sources":sum(bool(s["source_urls"]) and s["source_verified"] for s in scenes),
        "status":"ready_for_human_review" if scenes and unmatched==0 and not invalid and all(s["source_verified"] and s["source_urls"] for s in scenes) else "blocked_for_review",
        "notice":"No copyrighted videos are downloaded. RSS is unverified; no publication without manual licensing and fact checks."}
    save("research_leads.json",leads);save("storyboard.json",scenes)
    save("edit_decisions.json",timeline);save("qa_report.json",report)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    # Missing footage is an expected QA block, not an Actions infrastructure error.
if __name__=="__main__":main()
