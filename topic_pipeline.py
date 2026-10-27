"""Topic-only gaming documentary research gate. Does not fake a finished video."""
import argparse,json,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime,timezone
OUT=Path("agent_output")
def research(topic):
 url="https://news.google.com/rss/search?q="+urllib.parse.quote(topic+" game history")+"&hl=en-US&gl=US&ceid=US:en"
 req=urllib.request.Request(url,headers={"User-Agent":"DocumentaryResearch/0.2"})
 with urllib.request.urlopen(req,timeout=18) as r:root=ET.fromstring(r.read(1000000))
 return [{"title":e.findtext("title",""),"url":e.findtext("link",""),"date":e.findtext("pubDate",""),"verified":False} for e in root.findall(".//item")[:20] if e.findtext("link")]
def main():
 p=argparse.ArgumentParser();p.add_argument("--topic",required=True);p.add_argument("--minutes",type=int,default=12);a=p.parse_args()
 OUT.mkdir(exist_ok=True)
 try: leads=research(a.topic);err=None
 except Exception as e:leads=[];err=str(e)[:200]
 report={"topic":a.topic,"target_minutes":a.minutes,"generated_at":datetime.now(timezone.utc).isoformat(),"research_leads":leads,"structure":["hook","origin","characters","challenge","evidence","reversal","resolution"],"needs":["fact_checked_script","licensed_gameplay_footage","narration","visual_matching","render_qa"],"status":"BLOCKED_RESEARCH_OR_ASSETS_REQUIRED","error":err,"notice":"Headlines are unverified leads; no claim of video production. Do not publish without source and usage-right checks."}
 (OUT/"topic_plan.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({"topic":a.topic,"leads":len(leads),"status":report["status"]}))
if __name__=="__main__":main()
