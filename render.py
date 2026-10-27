"""GitHub Actions cloud documentary renderer. Real TTS timed to storyboard 15 s.
Optional Pexels API for real stock clips, otherwise self-generated title cards.
Never treats unlicensed or unavailable video footage as available.
"""
import asyncio,json,os,subprocess,tempfile,shutil,re,math
from pathlib import Path
import requests
from PIL import Image,ImageDraw,ImageFont
from media_assets import try_image
from open_video import fetch_video
from pixabay_video import fetch_pixabay_video
ROOT=Path(__file__).parent; OUT=ROOT/'output';OUT.mkdir(exist_ok=True)
SCENES=json.loads((ROOT/'scenes.json').read_text('utf-8'))
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
if not Path(FONT).exists(): FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
def run(cmd):subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
def length(f):
 p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nokey=1:noprint_wrappers=1',str(f)],capture_output=True,text=True,check=True)
 return float(p.stdout.strip())
def stamp(x):
 ms=round(x*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
def lines(text,lim=24):return '\n'.join(text[i:i+lim] for i in range(0,len(text),lim))
def frame(scene,dest):
 i=scene['scene'];im=Image.new('RGB',(1920,1080),(14,20,32));d=ImageDraw.Draw(im)
 for y in range(1080):
  shade=int(16+42*y/1080);d.line((0,y,1920,y),fill=(shade//2,shade*2//3,shade))
 d.ellipse((1130,-320,2080,630),outline=(124,94,57),width=9)
 d.rectangle((100,130,112,970),fill=(186,134,68))
 f1=ImageFont.truetype(FONT,72);f2=ImageFont.truetype(FONT,48);f3=ImageFont.truetype(FONT,33)
 d.text((155,135),'赫庫蘭尼姆：失落卷軸',font=f1,fill=(235,207,155))
 d.multiline_text((155,330),lines(scene['narration'],22),font=f2,fill=(245,245,240),spacing=20)
 d.text((155,955),f"SCENE {i:02d}/48  |  AI × 考古學 × 古典文獻",font=f3,fill=(192,169,128))
 im.save(dest)
def stock_video(q,out):
 key=os.getenv('PEXELS_API_KEY','').strip()
 if not key:return False
 try:
  r=requests.get('https://api.pexels.com/videos/search',params={'query':q,'per_page':3,'orientation':'landscape'},headers={'Authorization':key},timeout=18);r.raise_for_status()
  for item in r.json().get('videos',[]):
   vf=sorted([v for v in item.get('video_files',[]) if v.get('file_type')=='video/mp4' and v.get('width',0)>=1280],key=lambda z:abs(z.get('width',1920)-1920))
   if not vf:continue
   with requests.get(vf[0]['link'],stream=True,timeout=45) as s:
    s.raise_for_status()
    with open(out,'wb') as f:
     for chunk in s.iter_content(256*1024):f.write(chunk)
   if length(out)>2:return True
 except Exception as e:print('Optional footage failed:',str(e)[:150])
 return False
async def voice(text,out):
 if os.getenv('TTS_ENGINE','kokoro') == 'kokoro':
  from kokoro_voice import synthesize
 else:
  from piper_voice import synthesize
 await asyncio.to_thread(synthesize,text,out)
def main():
 clips=[];cues=[];time=0;credits=[];stock_count=0;commons_video_count=0;image_count=0;card_count=0
 work=Path(tempfile.mkdtemp())
 try:
  selected=SCENES[:2] if os.getenv('VOICE_PREVIEW','false') == 'true' else SCENES
  for i,s in enumerate(selected,1):
   print('Rendering scene',i,'/',len(SCENES),flush=True)
   audio=work/f'a{i}.wav';shot=work/f'shot{i}.jpg';stock=work/f'stock{i}.mp4';video=work/f'v{i}.mp4'
   asyncio.run(voice(s['narration'],audio))
   duration=length(audio)
   # Favor intelligibility. Audio >15 seconds is accelerated only moderately;
   # otherwise scene duration extends, and actual SRT is computed from real length.
   target=max(15,duration/1.20+0.3)
   speed=max(1,duration/(target-0.2))
   af=f'atempo={speed:.5f},apad=whole_dur={target:.3f},atrim=duration={target:.3f}'
   gotstock=stock_video(s['stock_query'],stock)
   if not gotstock:
    gotstock=fetch_pixabay_video(s['stock_query'],stock,credits,i)
   if not gotstock:
    gotstock=fetch_video(s['stock_query'],stock,credits,i)
    if gotstock:commons_video_count+=1
   if gotstock:
    stock_count+=1
    run(['ffmpeg','-y','-stream_loop','-1','-i',str(stock),'-i',str(audio),'-vf','scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=24,format=yuv420p','-af',af,'-t',str(target),'-c:v','libx264','-preset','ultrafast','-crf','29','-c:a','aac','-b:a','128k',str(video)])
   else:
    has_image=try_image(s['stock_query'],shot,credits,i)
    if has_image:
     image_count+=1
    else:
     card_count+=1
     frame(s,shot)
    run(['ffmpeg','-y','-loop','1','-framerate','24','-i',str(shot),'-i',str(audio),'-vf','scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,zoompan=z=\'min(zoom+0.0005,1.08)\':d=1:s=1920x1080:fps=24,format=yuv420p','-af',af,'-t',str(target),'-c:v','libx264','-preset','ultrafast','-crf','29','-c:a','aac','-b:a','128k',str(video)])
   clips.append(video);cues.append((time,time+target,s['narration']));time+=target
  concat=work/'list.txt';concat.write_text(''.join("file '"+str(v).replace("'","'\\''")+"'\n" for v in clips))
  run(['ffmpeg','-y','-f','concat','-safe','0','-i',str(concat),'-c','copy',str(OUT/'herculaneum_zh_tw.mp4')])
  (OUT/'herculaneum_actual_timing.srt').write_text('\n'.join(f'{i}\n{stamp(a)} --> {stamp(b)}\n{lines(txt,25)}\n' for i,(a,b,txt) in enumerate(cues,1)),encoding='utf-8')
  (OUT/'media_credits.json').write_text(json.dumps(credits,ensure_ascii=False,indent=2),encoding='utf-8')
  (OUT/'render_report.json').write_text(json.dumps({'seconds':time,'scenes':len(clips),'video_scenes':stock_count,'commons_video_scenes':commons_video_count,'wikimedia_image_scenes':image_count,'text_card_scenes':card_count,'note':'SRT uses actual rendered scene durations. External licensing must be reviewed.'},ensure_ascii=False,indent=2),encoding='utf-8')
 finally:shutil.rmtree(work,ignore_errors=True)
if __name__=='__main__':main()
