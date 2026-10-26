"""Narration normalization, optional ducked music and peak-safe mixing."""
from pathlib import Path
import subprocess
import numpy as np
from imageio_ffmpeg import get_ffmpeg_exe
from editor.runtime import AudioClip


def local_media(folder,extensions):
    folder = Path(folder)
    if not folder.resolve().is_relative_to(folder.parent.resolve()):
        raise ValueError("Thư mục nhạc/SFX vượt khỏi assets/.")
    folder = folder.resolve()
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in extensions and p.is_file() and p.resolve().is_relative_to(folder))


def build_audio(timeline,assets_dir,resources,*,motion=False):
    rate = 44100
    def read(path):
        # MoviePy 2.2.1's audio reader recursively indexes a boolean mask for
        # short WAV buffers (notably SFX). Decode PCM with its bundled FFmpeg
        # instead, keeping sample timing consistent for MP3/WAV/music alike.
        result = subprocess.run([get_ffmpeg_exe(),"-hide_banner","-loglevel","error","-i",str(path),
            "-vn","-t","900","-ac","2","-ar",str(rate),"-f","f32le","pipe:1"],capture_output=True,check=True,timeout=120)
        samples = np.frombuffer(result.stdout,dtype="<f4").reshape(-1,2).copy()
        if not len(samples):
            raise ValueError(f"Audio không có mẫu âm thanh: {Path(path).name}")
        return samples
    narration = np.zeros((int(np.ceil(timeline.duration*rate))+1,2),dtype=np.float32)
    for scene in timeline.scenes:
        samples = read(scene.audio)
        peak = float(np.max(np.abs(samples)))
        if peak > 1e-6:
            samples *= min(8.,.85/peak)
        start = round(scene.start*rate)
        length = min(len(samples),round(scene.duration*rate),len(narration)-start)
        narration[start:start+length] += samples[:length]
    mix = narration.copy()
    music_files = local_media(Path(assets_dir)/"music",{".mp3",".wav",".m4a",".ogg"})
    mood=timeline.plan.music.mood if hasattr(timeline.plan.music,"mood") else ""
    music_files.sort(key=lambda p: (not bool(mood and mood.casefold() in p.stem.casefold()),p.name))
    music = music_files[0] if music_files and timeline.plan.music.volume > 0 else None
    if music:
        samples = read(music)
        if len(samples):
            music_track = samples[np.arange(len(mix))%len(samples)]
            music_track /= max(1.,float(np.max(np.abs(music_track))))
            block,envelope,gain = 882,[],1.
            for offset in range(0,len(narration),block):
                speech = np.sqrt(np.mean(narration[offset:offset+block]**2)) > .012
                gain += ((.22 if speech else 1.)-gain)*(.65 if speech else .08)
                envelope.append(gain)
            duck = np.interp(np.arange(len(mix)),np.arange(len(envelope))*block,envelope)
            render_style = getattr(timeline.plan, "render_style", None)
            if render_style is not None and not render_style.ducking:
                duck = np.ones_like(duck)
            fade = np.minimum(1.,np.minimum(np.arange(len(mix))/(rate*.7),(len(mix)-1-np.arange(len(mix)))/(rate*.8)))
            volume=timeline.plan.style_profile.audio.music_volume if motion and timeline.plan.style_profile else timeline.plan.music.volume
            mix += music_track*duck[:,None]*fade[:,None]*volume
    sfx_files=local_media(Path(assets_dir)/"sfx",{".mp3",".wav",".ogg"})
    events=[]
    for scene in timeline.scenes:
        if scene.spec.sfx != "none": events.append((scene.start,scene.spec.sfx))
        for shot in getattr(scene,"shots",[]):
            visual=getattr(shot.spec,"visual",None)
            style=getattr(timeline.plan,"render_style",None)
            if style and not style.visual_templates: continue
            if not visual or visual.template=="stock": continue
            if motion and visual.beats:
                last=-10.
                for beat in sorted(visual.beats,key=lambda b:b.at_sec if b.at_sec is not None else 0):
                    if beat.at_sec is None or not (beat.action in {"reveal","strike_replace","count_up","mascot_surprised"} or beat.action.startswith("reveal_item_")): continue
                    when=scene.start+beat.at_sec
                    if when-last<.35: continue
                    kind="whoosh" if visual.template=="source_card" else "click" if visual.template=="timeline" else "chime" if beat.action=="strike_replace" else "pop"
                    events.append((when,kind));last=when
                continue
            from editor.templates.core import element_times
            kind="whoosh" if visual.template=="source_card" else "pop"
            events.extend((shot.start+t,kind) for t in element_times(visual.template,visual.data.model_dump(mode="json"),shot.duration))
        v_plan = getattr(scene.spec, "visual_plan", None)
        if motion and v_plan:
            last = -10.0
            plan_beats = getattr(v_plan, "beats", []) or []
            for beat in sorted(plan_beats, key=lambda b: b.at_sec if b.at_sec is not None else 0):
                if beat.at_sec is None: continue
                when = scene.start + beat.at_sec
                if when - last < 0.28: continue
                act = str(beat.action).lower()
                if any(k in act for k in ("whoosh", "entrance", "fly_in", "slide_up", "zoom")):
                    kind = "whoosh"
                elif any(k in act for k in ("stamp", "strike", "snap", "clash")):
                    kind = "snap"
                elif any(k in act for k in ("chime", "complete", "check", "success", "ring")):
                    kind = "chime"
                elif any(k in act for k in ("click", "switch", "tick", "type")):
                    kind = "click"
                else:
                    kind = "pop"
                events.append((when, kind))
                last = when
    for time,kind in sorted(set(events)):
        files = [p for p in sfx_files if p.stem == kind]
        if files:
            samples = read(files[0])
            samples *= .18/max(1e-6,float(np.max(np.abs(samples))))
            offset = round(time*rate)
            if offset<0 or offset>=len(mix): continue
            length = min(len(samples),len(mix)-offset)
            mix[offset:offset+length] += samples[:length]
    ramp = np.minimum(1.,np.minimum(np.arange(len(mix))/(rate*.025),(len(mix)-1-np.arange(len(mix)))/(rate*.08)))
    mix *= ramp[:,None]
    mix *= min(1.,.98/max(1e-6,float(np.max(np.abs(mix)))))
    def frame(t):
        indices = np.clip((np.asarray(t)*rate).astype(int),0,len(mix)-1)
        return mix[indices]
    return AudioClip(frame,duration=timeline.duration,fps=rate),music
