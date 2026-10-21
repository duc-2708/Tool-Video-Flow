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
from PIL import Image
from proglog import ProgressBarLogger

from config.settings import get_settings
from editor.timeline import build_timeline, confined
from editor.effects import cover, color_card, transition
from editor.captions import Captions, find_font
from editor.audio_mix import build_audio
from editor.runtime import VideoClip, VideoFileClip
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
    def __init__(self,timeline,size,font,diagnostics):
        self.timeline,self.size,self.font,self.diagnostics = timeline,size,font,diagnostics
        self.cache = OrderedDict()

    def close(self):
        for source in self.cache.values():
            if isinstance(source,VideoFileClip):
                source.close()
        self.cache.clear()

    def frame(self,shot,t):
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
        return cover(frame,self.size,shot.spec.effect,local/shot.duration)

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
        render_dir = confined(timeline.project,"render")
        render_dir.mkdir(exist_ok=True)
        # Avoid simultaneous CLI/UI writers for this project; inputs never locked/modified.
        with file_lock(render_dir/"editor.lock"):
            portrait = timeline.plan.format == "tiktok"
            size = ((540,960) if portrait else (960,540)) if mode == "preview" else ((1080,1920) if portrait else (1920,1080))
            font = find_font(settings.root_dir)
            captions = Captions(timeline,size,font)
            frames = Frames(timeline,size,font,diagnostics)
            notify(.05,"Đang chuẩn hóa giọng đọc và trộn nhạc")
            audio,music = build_audio(timeline,settings.root_dir/"assets",resources)
            resources.append(audio)
            video = VideoClip(lambda t: captions.apply(frames.at(t),t),duration=timeline.duration).with_audio(audio).with_fps(30)
            filename = f"{slugify(timeline.plan.title)}_{timeline.plan.format}_{mode}.mp4"
            destination = confined(render_dir,filename)
            temporary = confined(render_dir,f".{uuid.uuid4().hex}.mp4")
            temp_audio = confined(render_dir,f".{uuid.uuid4().hex}.m4a")
            try:
                video.write_videofile(str(temporary),fps=30,codec="libx264",audio_codec="aac",
                    audio_bitrate="192k",preset="ultrafast" if mode == "preview" else "medium",
                    threads=min(8,os.cpu_count() or 2),temp_audiofile=str(temp_audio),
                    ffmpeg_params=["-crf","27" if mode == "preview" else "20","-movflags","+faststart"],
                    pixel_format="yuv420p",logger=RenderProgress(notify))
                replace_file_retry(temporary, destination)
            finally:
                discard_temp_file(temp_audio)
            original_credits = confined(timeline.project,"credits.txt")
            credits = original_credits.read_text(encoding="utf-8") if original_credits.is_file() else "Chưa có credits.txt của Assets.\n"
            credits += f"\n--- Render ---\nFont: {font.name}\nNhạc nền: {music.name if music else 'Không sử dụng'}\n"
            write_text_atomic(confined(render_dir,"credits.txt"), credits)
            result = {"path":str(destination),"filename":filename,"mode":mode,"duration_sec":timeline.duration,
                "width":size[0],"height":size[1],"fps":30,"size_bytes":destination.stat().st_size,
                "render_seconds":round(time.perf_counter()-started,3),"warnings":timeline.warnings,
                "caption_timing":"Word sidecar nếu hợp lệ; còn lại ước lượng theo số ký tự"}
            write_json(confined(render_dir,f"{mode}.json"),result)
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
