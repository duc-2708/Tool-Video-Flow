"""Stage 5: local MoviePy 2 editor. Inputs are immutable; all products go in render/."""
from utils.atomic_io import discard_temp_file, replace_file_retry, write_text_atomic
import argparse
from collections import OrderedDict
from pathlib import Path
import json
import os
import subprocess
import time
import uuid

import numpy as np
from PIL import Image,ImageFilter,ImageEnhance
from proglog import ProgressBarLogger

from config.settings import get_settings
from editor.timeline import build_timeline, confined
from editor.effects import cover, color_card, transition
from editor.captions import Captions, find_font
from editor.audio_mix import build_audio
from editor.runtime import VideoClip, VideoFileClip
from editor.templates.core import Card
from editor.templates.theme import load_theme
from editor.graphics import prepare_graphics,ProgressTracker
from utils.cache import write_json
from utils.console import configure_console
from utils.diagnostics import Diagnostics
from utils.file_lock import file_lock
from utils.text import slugify


class RenderProgress(ProgressBarLogger):
    def __init__(self, notify):
        super().__init__()
        self.notify,self.last = notify,0.

    def bars_callback(self,bar,attr,value,old_value=None):
        if attr != "index":
            return
        total = self.bars[bar].get("total",1) or 1
        now = time.monotonic()
        if now-self.last > .3 or value >= total:
            fraction = min(1.,value/total)
            self.notify((.18+.78*fraction) if bar == "frame_index" else (.08+.10*fraction),
                        "Đang dựng hình" if bar == "frame_index" else "Đang ghép âm thanh")
            self.last = now


class Frames:
    """At most two decoders/cards resident, including during scene transitions."""
    def __init__(self,timeline,size,font,diagnostics,theme=None):
        self.timeline,self.size,self.font,self.diagnostics = timeline,size,font,diagnostics
        self.cache = OrderedDict()
        self.theme=theme or load_theme()
        self.cards=OrderedDict()
        self.failed_cards=set()
        self.motion_paths={}
        self.motion_readers=OrderedDict()

    def close(self):
        for reader in self.motion_readers.values(): reader.close()
        self.motion_readers.clear()
        for source in self.cache.values():
            if isinstance(source,VideoFileClip):
                source.close()
        self.cache.clear()
        self.cards.clear()

    def frame(self,shot,t):
        if shot.scene_id in self.motion_paths:
            if shot.scene_id not in self.motion_readers:
                if len(self.motion_readers)>=2:
                    _,old=self.motion_readers.popitem(last=False);old.close()
                self.motion_readers[shot.scene_id]=VideoFileClip(str(self.motion_paths[shot.scene_id]),audio=False)
            self.motion_readers.move_to_end(shot.scene_id)
            reader=self.motion_readers[shot.scene_id]
            scene=next(s for s in self.timeline.scenes if s.spec.id==shot.scene_id)
            return reader.get_frame(min(max(0,t-scene.start),max(0,reader.duration-1/reader.fps)))
        key = (shot.scene_id,shot.shot_id)
        text = shot.spec.text_overlay or next(s.spec.narration for s in self.timeline.scenes if s.spec.id == shot.scene_id)
        if key not in self.cache:
            while len(self.cache) >= 2:
                _,old = self.cache.popitem(last=False)
                if isinstance(old,VideoFileClip):
                    old.close()
            try:
                if shot.fallback:
                    source = color_card(self.size,text,self.font,shot.scene_id)
                elif shot.path.suffix.lower() in {".mp4",".mov",".webm",".mkv"}:
                    source = VideoFileClip(str(shot.path),audio=False)
                    if not source.duration or source.duration <= 0:
                        source.close()
                        raise ValueError("Clip nguồn không có thời lượng hợp lệ.")
                else:
                    with Image.open(shot.path) as image:
                        source = np.asarray(image.convert("RGB"))
                self.cache[key] = source
            except Exception as error:
                self.diagnostics.record_exception(error,f"Đọc clip cảnh {shot.scene_id}, shot {shot.shot_id}; chuyển nền màu")
                warning = f"Cảnh {shot.scene_id}, shot {shot.shot_id}: clip hỏng, dùng nền màu."
                if warning not in self.timeline.warnings:
                    self.timeline.warnings.append(warning)
                self.cache[key] = color_card(self.size,text,self.font,shot.scene_id)
        self.cache.move_to_end(key)
        source = self.cache[key]
        local = max(0.,min(t-shot.start,shot.duration))
        if isinstance(source,VideoFileClip):
            # Slight shortage: smooth slowdown. Larger shortage: deterministic loop.
            sample = local*source.duration/shot.duration if source.duration < shot.duration <= source.duration*1.25 else local % source.duration
            frame = source.get_frame(min(sample,max(0.,source.duration-1/source.fps)))
        else:
            frame = source
        visual=shot.spec.visual
        if visual and visual.template!="stock" and (not self.timeline.plan.render_style or self.timeline.plan.render_style.visual_templates):
            if key in self.failed_cards:
                return color_card(self.size,"Tìm hiểu diễn biến và tác động",self.font,shot.scene_id)
            try:
                return self.graphic_frame(shot,key,visual,frame,local)
            except Exception as error:
                self.diagnostics.record_exception(error,f"Mẫu đồ họa cảnh {shot.scene_id}, shot {shot.shot_id}; chuyển nền an toàn")
                warning=f"Cảnh {shot.scene_id}, shot {shot.shot_id}: mẫu đồ họa không dựng được, dùng nền màu trung tính."
                if warning not in self.timeline.warnings: self.timeline.warnings.append(warning)
                self.failed_cards.add(key)
                return color_card(self.size,"Tìm hiểu diễn biến và tác động",self.font,shot.scene_id)
        return cover(frame,self.size,shot.spec.effect,local/shot.duration)

    def graphic_frame(self,shot,key,visual,frame,local):
        if key not in self.cards:
            if len(self.cards)>=2: self.cards.popitem(last=False)
            self.cards[key]=Card(visual.template,visual.data,shot.duration,self.size,self.theme)
        card=self.cards[key]
        if shot.fallback:
            return card.frame(local)
        # Stock is a supporting, darkened moving background, never foreground.
        base=cover(frame,self.size,"zoom_in",local/shot.duration)
        base=ImageEnhance.Brightness(Image.fromarray(base).filter(ImageFilter.GaussianBlur(max(1,self.size[0]/180)))).enhance(.32).convert("RGBA")
        return np.asarray(Image.alpha_composite(base,card.frame(local,transparent=True)).convert("RGB"))

    def at(self,t):
        scene_index = next((i for i,s in enumerate(self.timeline.scenes) if t < s.start+s.duration),len(self.timeline.scenes)-1)
        scene = self.timeline.scenes[scene_index]
        shot = next((s for s in scene.shots if t < s.start+s.duration),scene.shots[-1])
        frame = self.frame(shot,t)
        remaining = scene.start+scene.duration-t
        if scene_index+1 < len(self.timeline.scenes) and remaining < .22 and scene.spec.transition_out != "cut":
            following = self.timeline.scenes[scene_index+1].shots[0]
            # Transition consumes the outgoing tail, never overlaps narration or shortens scenes.
            next_frame = self.frame(following,following.start)
            frame = transition(frame,next_frame,1-remaining/.22,scene.spec.transition_out)
        return frame


def run_render(plan_path,*,mode="preview",settings=None,progress=None,diagnostics=None):
    if mode not in {"preview","final"}:
        raise ValueError("Chế độ phải là preview hoặc final.")
    settings = settings or get_settings()
    diagnostics = diagnostics or Diagnostics(settings.logs_dir,filename="render_errors.log")
    notify = progress or (lambda value,message: None)
    resources,frames,video = [],None,None
    started = time.perf_counter()
    temporary = None
    try:
        notify(.01,"Đang kiểm tra audio và timeline")
        timeline = build_timeline(Path(plan_path))
        prepare_graphics(timeline,diagnostics)
        render_dir = confined(timeline.project,"render")
        render_dir.mkdir(exist_ok=True)
        # Avoid simultaneous CLI/UI writers for this project; inputs never locked/modified.
        with file_lock(render_dir/"editor.lock"):
            portrait = timeline.plan.format == "tiktok"
            size = ((540,960) if portrait else (960,540)) if mode == "preview" else ((1080,1920) if portrait else (1920,1080))
            if settings.motion_enabled:
                full=(1080,1920) if portrait else (1920,1080)
                size=tuple(max(2,round(n*settings.motion_scale/2)*2) for n in full)
            font = find_font(settings.root_dir)
            theme=load_theme(timeline.plan.render_style.theme,settings.root_dir)
            captions = Captions(timeline,size,font)
            frames = Frames(timeline,size,font,diagnostics,theme)
            motion_results=[]
            if settings.motion_enabled and timeline.plan.render_style.visual_templates:
                from pipeline.render_motion import render_scene,SUPPORTED
                candidates=[s for s in timeline.scenes if any(shot.spec.visual and shot.spec.visual.template in SUPPORTED for shot in s.shots)]
                paths={}
                for index,scene in enumerate(candidates):
                    def static_frame(t,scene=scene):
                        shot=next((s for s in scene.shots if scene.start+t<s.start+s.duration),scene.shots[-1])
                        return captions.apply(frames.frame(shot,scene.start+t),scene.start+t)
                    def motion_progress(value,message,index=index):
                        notify(.05+.45*(index+value)/max(1,len(candidates)),message)
                    caption_style=captions.style.model_copy(update={"enabled":True}) if scene.audio_silent else captions.style
                    result=render_scene(scene,render_dir/"motion_cache",size=size,font=font,caption_style=caption_style,
                        fps=settings.motion_fps,static_frame=static_frame,progress=motion_progress,diagnostics=diagnostics,
                        extra_identity={"theme":theme,"scene":scene.spec.model_dump(mode="json")})
                    if result:
                        paths[scene.spec.id]=result["path"];motion_results.append(result)
                    else:
                        timeline.warnings.append(f"Cảnh {scene.spec.id}: Motion không sẵn sàng; dùng đồ họa Pillow hiện có. Kiểm tra Playwright/Chromium và logs/render_errors.log.")
                frames.motion_paths=paths
            tracker=ProgressTracker(timeline,size,theme)
            notify(.05,"Đang chuẩn hóa giọng đọc và trộn nhạc")
            audio,music = build_audio(timeline,settings.root_dir/"assets",resources)
            resources.append(audio)
            fps=15 if mode=="preview" else 30
            if settings.motion_enabled: fps=settings.motion_fps
            def composite(t):
                scene=next((s for s in timeline.scenes if t<s.start+s.duration),timeline.scenes[-1])
                frame=frames.at(t)
                if scene.spec.id not in frames.motion_paths: frame=captions.apply(frame,t)
                return tracker.apply(frame,t)
            video = VideoClip(composite,duration=timeline.duration).with_audio(audio).with_fps(fps)
            filename = f"{slugify(timeline.plan.title)}_{timeline.plan.format}_{mode}.mp4"
            destination = confined(render_dir,filename)
            temporary = confined(render_dir,f".{uuid.uuid4().hex}.mp4")
            temp_audio = confined(render_dir,f".{uuid.uuid4().hex}.m4a")
            try:
                video.write_videofile(str(temporary),fps=fps,codec="libx264",audio_codec="aac",
                    audio_bitrate="192k",preset="ultrafast" if mode == "preview" else "medium",
                    threads=min(8,os.cpu_count() or 2),temp_audiofile=str(temp_audio),
                    ffmpeg_params=["-crf","27" if mode == "preview" else "20","-movflags","+faststart"],
                    pixel_format="yuv420p",logger=RenderProgress((lambda value,message:notify(.5+.5*value,message)) if settings.motion_enabled else notify))
                replace_file_retry(temporary, destination)
            finally:
                discard_temp_file(temp_audio)
            original_credits = confined(timeline.project,"credits.txt")
            credits = original_credits.read_text(encoding="utf-8") if original_credits.is_file() else "Chưa có credits.txt của Assets.\n"
            credits += f"\n--- Render ---\nFont: {font.name}\nNhạc nền: {music.name if music else 'Không sử dụng'}\n"
            write_text_atomic(confined(render_dir,"credits.txt"), credits)
            result = {"path":str(destination),"filename":filename,"mode":mode,"duration_sec":timeline.duration,
                "width":size[0],"height":size[1],"fps":fps,"size_bytes":destination.stat().st_size,
                "render_seconds":round(time.perf_counter()-started,3),"warnings":timeline.warnings,
                "caption_timing":"Word sidecar nếu hợp lệ; còn lại ước lượng theo số ký tự"}
            if settings.motion_enabled:
                result.update(motion_enabled=True,motion_scenes=motion_results,motion_scale=settings.motion_scale)
            write_json(confined(render_dir,f"{mode}.json"),result)
            reviews=getattr(timeline,"visual_review",[])
            write_json(confined(render_dir,"visual_review.json"),{"shots":reviews,"warnings":timeline.warnings})
            write_text_atomic(confined(render_dir,"report.md"),"# Kiểm tra đồ họa khi Render\n\n"+
                "\n".join(f"- {message}" for message in timeline.warnings)+"\n\nĐầu vào Edit Plan, audio, clips và credits được giữ nguyên.\n")
            notify(1.,"Render hoàn tất")
            return result
    except Exception as error:
        diagnostics.record_exception(error,"Editor render thất bại")
        if isinstance(error,subprocess.CalledProcessError) and error.stderr:
            diagnostics.record("FFmpeg stderr:\n"+error.stderr.decode("utf-8",errors="replace"))
        raise
    finally:
        if video:
            video.close()
        if frames:
            frames.close()
        for resource in reversed(resources):
            resource.close()
        if temporary:
            discard_temp_file(temporary)


def main():
    configure_console()
    parser = argparse.ArgumentParser(description="Dựng video local từ resolved plan; không thay đổi Assets.")
    parser.add_argument("plan",type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--mode",choices=["preview","final"],default="preview")
    modes.add_argument("--preview",action="store_true")
    modes.add_argument("--final",action="store_true")
    parser.add_argument("--debug",action="store_true")
    args = parser.parse_args()
    try:
        settings = get_settings()
    except Exception:
        print("Cấu hình không hợp lệ. Kiểm tra kiểu và khoảng giá trị theo .env.example; không in nội dung cấu hình.")
        raise SystemExit(1) from None
    diagnostics = Diagnostics(settings.logs_dir,debug=args.debug,filename="render_errors.log")
    last = [-1]
    def progress(value,message):
        percent = int(value*100)
        if percent >= last[0]+5 or percent == 100:
            print(f"{percent:3d}% · {message}",flush=True)
            last[0] = percent
    try:
        result = run_render(args.plan,mode="final" if args.final else args.mode,settings=settings,diagnostics=diagnostics,progress=progress)
        print(f"Đã lưu: {result['path']}\nThời lượng: {result['duration_sec']:.2f}s · {result['width']}x{result['height']} · Render: {result['render_seconds']:.1f}s")
        for warning in result["warnings"]:
            print(diagnostics.redact(warning))
    except Exception as error:
        print("Render thất bại: "+diagnostics.redact(str(error)))
        print("Xem lỗi gốc trong logs/render_errors.log; thêm --debug để xem traceback.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
