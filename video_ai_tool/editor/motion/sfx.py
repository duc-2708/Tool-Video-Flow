"""Original, quiet mathematical SFX; never fetches copyrighted audio."""
from pathlib import Path
import wave
import numpy as np


def synthesize(kind,rate=44100):
    seconds={"click":.045,"pop":.12,"whoosh":.25,"chime":.32}.get(kind,.12)
    t=np.arange(round(seconds*rate))/rate
    if kind=="whoosh":
        signal=np.random.default_rng(23).normal(0,.18,len(t))*np.sin(np.pi*t/seconds)**2
        signal=np.convolve(signal,np.ones(12)/12,mode="same")
    elif kind=="chime": signal=(np.sin(2*np.pi*880*t)+.35*np.sin(2*np.pi*1320*t))*np.exp(-t*15)
    elif kind=="click": signal=np.sin(2*np.pi*1800*t)*np.exp(-t*140)
    else: signal=np.sin(2*np.pi*(440*t-900*t*t))*np.exp(-t*30)
    signal*=np.minimum(1,t/.004)*np.minimum(1,(seconds-t)/.012)
    return (signal*.12/max(1e-6,float(np.max(np.abs(signal))))).astype(np.float32)


def ensure_sfx(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    for kind in ("click","pop","whoosh","chime"):
        # A user's own sound of any supported extension takes precedence.
        if any((folder/(kind+ext)).exists() for ext in (".wav",".mp3",".ogg")): continue
        with wave.open(str(folder/(kind+".wav")),"wb") as audio:
            audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(44100)
            audio.writeframes((synthesize(kind)*32767).astype("<i2").tobytes())
    note=folder/"GENERATED_SFX_LICENSE.txt"
    if not note.exists(): note.write_text("Original synthesized sine/noise SFX created by editor/motion/sfx.py, CC0 1.0. No samples, music or third-party recordings. Existing user files retain their own licenses.\n",encoding="utf-8")
