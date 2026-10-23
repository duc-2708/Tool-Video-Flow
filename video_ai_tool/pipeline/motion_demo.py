"""Offline 10-second scene benchmark; input project remains byte-for-byte intact."""
import argparse
from copy import deepcopy
import hashlib
from pathlib import Path
import shutil
from config.settings import ROOT_DIR
from editor.timeline import build_timeline,Timeline
from editor.graphics import prepare_graphics
from editor.captions import find_font,Captions
from editor.render import Frames
from editor.audio_mix import build_audio
from editor.runtime import VideoFileClip
from editor.motion.memory import MemorySampler
from pipeline.render_motion import render_scene,browser_page,capture,scene_payload
from utils.atomic_io import write_json_atomic
from utils.console import configure_console
from utils.diagnostics import Diagnostics


def run_demo(plan,*,scene_id=None,duration=10.,scales=(1.,.5),output=None):
    output=Path(output or ROOT_DIR/"output/motion_demo");output.mkdir(parents=True,exist_ok=True)
    original=build_timeline(Path(plan));diagnostics=Diagnostics(ROOT_DIR/"logs",filename="render_errors.log")
    inputs={Path(plan),original.project/"assets.json",original.project/"brief.json",original.project/"credits.txt"}
    inputs.update(s.audio for s in original.scenes)
    inputs.update(shot.path for s in original.scenes for shot in s.shots if shot.path)
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs if p.is_file()}
    prepare_graphics(original,diagnostics)
    source=next((s for s in original.scenes if s.spec.id==scene_id),original.scenes[0])
    scene=deepcopy(source);scene.start=0.;factor=duration/source.duration;scene.duration=duration
    from utils.word_timing import save_words,read_words,align_words
    words,_=align_words(source.spec.narration,source.duration,read_words(source.audio.with_suffix(".words.json")))
    audio_dir=output/"audio";audio_dir.mkdir(exist_ok=True)
    scene.audio=audio_dir/f"scene_{scene.spec.id}.mp3";shutil.copyfile(source.audio,scene.audio)
    from utils.word_timing import timing_source
    save_words(scene.audio.with_suffix(".words.json"),source.spec.narration,duration,words,
        source=timing_source(source.audio.with_suffix(".words.json")))
    for shot in scene.shots:
        shot.start=(shot.start-source.start)*factor;shot.duration*=factor
    # Benchmark repeats no speech: existing audio is cut/padded with silence by audio_mix.
    # Its captions keep actual audio timing rather than pretending a 10s voice recording.
    timeline=Timeline(original.plan,original.project,[scene],duration,[])
    font=find_font(ROOT_DIR);style=original.plan.render_style.captions
    records=[]
    for scale in scales:
        full=(1080,1920) if original.plan.format=="tiktok" else (1920,1080)
        size=tuple(round(n*scale/2)*2 for n in full)
        frames=Frames(timeline,size,font,diagnostics);captions=Captions(timeline,size,font)
        def static(t):
            shot=next((s for s in scene.shots if t<s.start+s.duration),scene.shots[-1])
            return captions.apply(frames.frame(shot,t),t)
        try:
            with MemorySampler() as memory:
                result=render_scene(scene,output/"cache",size=size,font=font,caption_style=style,fps=30,
                    static_frame=static,diagnostics=diagnostics,progress=lambda v,m:print(m,flush=True))
            if not result: raise RuntimeError("Chromium không dựng được demo; xem logs/render_errors.log.")
            destination=output/f"scene_{scene.spec.id}_scale_{scale:g}.mp4"
            resources=[];video=None
            try:
                audio,music=build_audio(timeline,ROOT_DIR/"assets",resources);resources.append(audio)
                video=VideoFileClip(result["path"],audio=False).with_duration(duration).with_audio(audio)
                video.write_videofile(str(destination),fps=30,codec="libx264",audio_codec="aac",preset="ultrafast",
                    pixel_format="yuv420p",ffmpeg_params=["-movflags","+faststart"],logger=None)
            finally:
                if video: video.close()
                for resource in resources: resource.close()
            payload=scene_payload(scene,size,style)
            with browser_page(size) as page:
                capture(page,payload,font)
                hashes=[]
                for t in (2.1,.1,2.1):
                    page.evaluate("t => renderAt(t)",t);hashes.append(hashlib.sha256(page.screenshot()).hexdigest())
                page.screenshot(path=str(output/f"scene_{scene.spec.id}_scale_{scale:g}.png"))
            records.append(dict(result,demo_path=str(destination),scale=scale,peak_tree_working_set_mb=memory.peak_mb,
                deterministic_hash_match=hashes[0]==hashes[2],frame_hash=hashes[0]))
        finally: frames.close()
    unchanged=all(Path(p).is_file() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in before.items())
    report={"project":str(original.project),"scene_id":scene.spec.id,"duration_sec":duration,"fps":30,
        "input_files_unchanged":unchanged,"input_files_checked":len(before),
        "audio_note":"Audio cảnh gốc, cắt/pad im lặng tới 10s; không tạo giọng mới. Benchmark đồ họa không phải video kịch bản mới.",
        "memory_note":"Đỉnh tổng working set Python + tiến trình con, lấy mẫu 250ms; có thể đếm trùng trang chia sẻ; không gồm toàn hệ thống.","runs":records}
    write_json_atomic(output/"benchmark.json",report)
    return report


def main():
    configure_console();parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan",type=Path);parser.add_argument("--scene",type=int)
    parser.add_argument("--output",type=Path);args=parser.parse_args()
    result=run_demo(args.plan,scene_id=args.scene,output=args.output)
    for run in result["runs"]:
        print(f"Scale {run['scale']}: {run['render_seconds']}s; RAM ~{run['peak_tree_working_set_mb']} MB; {run['demo_path']}")


if __name__=="__main__": main()
