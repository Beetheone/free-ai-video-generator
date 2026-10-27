"""Kokoro-82M-v1.1-zh Mandarin speech on GitHub CPU runners.
Apache-2.0 model. Keeps model loaded for subsequent scenes.
"""
import os,re
import numpy as np
import soundfile as sf
from functools import lru_cache
from opencc import OpenCC

@lru_cache(maxsize=1)
def get_pipeline():
    from kokoro import KPipeline
    return KPipeline(lang_code="z", repo_id="hexgrad/Kokoro-82M-v1.1-zh", device="cpu")

def synthesize(text, output):
    text = OpenCC("t2s").convert(text)
    pipe=get_pipeline()
    voice=os.getenv("KOKORO_VOICE","zf_094")
    chunks=[]
    for result in pipe(text,voice=voice,speed=0.97,split_pattern=r'(?<=[。！？；])'):
        audio=getattr(result,"audio",None)
        if audio is None:continue
        if hasattr(audio,"detach"):
            audio=audio.detach().cpu().numpy()
        arr=np.asarray(audio,dtype=np.float32)
        if arr.size:
            chunks.append(arr)
            chunks.append(np.zeros(2400,dtype=np.float32))
    if not chunks:raise RuntimeError("Kokoro produced no speech")
    sf.write(str(output),np.concatenate(chunks),24000)
