"""Full 60s local benchmark in a NEW project; no network or model requests."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from imageio_ffmpeg import get_ffmpeg_exe
from config.settings import get_settings
from editor.timeline import build_timeline
from editor.render import run_render
from editor.motion.memory import MemorySampler
from pipeline.projects import create_project
from pipeline.assets import _remap_audio_shots,persist
from schemas.assets import AssetsManifest
from utils.atomic_io import write_json_atomic,write_text_atomic
from utils.word_timing import read_words,align_words,save_words,timing_source
from utils.console import configure_console
from utils.diagnostics import Diagnostics


def benchmark_audio(source,target,original_duration,count,rate=44100):
    length=count/rate;speed=original_duration/length
    subprocess.run([get_ffmpeg_exe(),"-hide_banner","-loglevel","error","-y","-i",str(source),
        "-af",f"aresample={rate},atempo={speed:.10f},apad,atrim=end_sample={count}","-ar",str(rate),"-ac","2","-c:a","pcm_s16le",str(target)],check=True,capture_output=True,timeout=90)
    from utils.media import measured_audio_duration
    if abs(measured_audio_duration(target)-length)>.002:
        raise ValueError("Audio benchmark sai độ dài sample; dừng trước render.")
    return speed


def benchmark(source,settings,seconds=60.):
    timeline=build_timeline(Path(source));root=timeline.project
    inputs=[root/name for name in ("edit_plan.json","edit_plan.resolved.json","assets.json","credits.txt","brief.json")]
    inputs += [p for folder in (root/"audio",root/"clips") if folder.exists() for p in folder.iterdir() if p.is_file()]
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs if p.is_file()}
    project=create_project(settings.output_dir,"motion-v2-"+timeline.plan.title)
    for name in ("edit_plan.json","brief.json","sources.json"):
        if (root/name).is_file(): shutil.copyfile(root/name,project/name)
    shutil.copytree(root/"clips",project/"clips",dirs_exist_ok=True)
    (project/"audio").mkdir(exist_ok=True)
    plan=timeline.plan.model_copy(deep=True)
    manifest=AssetsManifest.model_validate_json((root/"assets.json").read_text(encoding="utf-8"))
    rate=44100;total=round(seconds*rate);cursor=0;changes=[]
    for i,scene in enumerate(timeline.scenes):
        count=total-cursor if i==len(timeline.scenes)-1 else round(total*scene.duration/timeline.duration)
        length=count/rate;cursor+=count
        target=project/"audio"/f"scene_{scene.spec.id}.wav"
        speed=benchmark_audio(scene.audio,target,scene.duration,count,rate)
        observed,_=align_words(scene.spec.narration,scene.duration,read_words(scene.audio.with_suffix(".words.json")))
        save_words(target.with_suffix(".words.json"),scene.spec.narration,length,
            [dict(w,start=w["start"]/speed,end=min(length,w["end"]/speed)) for w in observed],source="time_scaled_"+timing_source(scene.audio.with_suffix(".words.json")))
        record=next(r for r in manifest.scenes if r.scene_id==scene.spec.id)
        plan.scenes[i]=_remap_audio_shots(scene.spec,record,length)
        record.audio_path=target.relative_to(project).as_posix()
        changes.append({"scene_id":scene.spec.id,"original_sec":scene.duration,"benchmark_sec":length,"atempo":speed})
    plan.requested_duration_sec=seconds
    diagnostics=Diagnostics(settings.logs_dir,filename="render_errors.log")
    persist(project,plan,manifest,diagnostics,motion_enabled=True)
    note="Benchmark riêng: giữ toàn bộ lời đọc, atempo đồng đều để audio tổng đúng 60s; không phải bản production mới hoặc lời đọc do LLM viết lại. Không gọi API."
    report={"source_project":str(root),"benchmark_project":str(project),"original_duration_sec":timeline.duration,
        "duration_sec":seconds,"audio_note":note,"audio_changes":changes,"runs":[]}
    write_json_atomic(project/"benchmark.json",report)
    last=[0.]
    import time
    def progress(v,m):
        if time.monotonic()-last[0]>4 or v==1:
            print(f"{v:.0%} {m}",flush=True);last[0]=time.monotonic()
    for scale in (.5,1.):
        options=settings.model_copy(update={"motion_enabled":True,"motion_scale":scale,"motion_fps":30,"render_width":1080,"render_height":1920})
        with MemorySampler() as memory:
            result=run_render(project/"edit_plan.resolved.json",settings=options,mode="preview",progress=progress,diagnostics=diagnostics)
        tag=str(scale).replace(".","_")
        video=project/"render"/f"motion_scale_{tag}.mp4";shutil.copyfile(result["path"],video)
        sheet=project/"review_frames"/f"contact_sheet_scale_{tag}.png";shutil.copyfile(result["contact_sheet"],sheet)
        result.update(scale=scale,benchmark_path=str(video),benchmark_contact_sheet=str(sheet),peak_tree_working_set_mb=memory.peak_mb)
        report["runs"].append(result)
        report["input_files_unchanged"]=all(Path(p).is_file() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in before.items())
        report["input_files_checked"]=len(before)
        write_json_atomic(project/"benchmark.json",report)
        print(f"Scale {scale}: {result['render_seconds']}s; {video}",flush=True)
    lines=["# Motion v2 — benchmark local", "", note,"",f"Nguồn: {root}","", "| Scale | Kích thước | Giây video | Giây render | RAM cây tiến trình MB |", "|---|---|---|---|---|"]
    for r in report["runs"]: lines.append(f"| {r['scale']} | {r['width']}×{r['height']} | {r['duration_sec']:.3f} | {r['render_seconds']} | {r['peak_tree_working_set_mb']} |")
    lines += ["", "Input gốc không đổi: "+str(report["input_files_unchanged"]),"", "## Ghi chú/cảnh báo", ""]
    lines += ["- "+n for n in report["runs"][-1]["warnings"]]
    write_text_atomic(project/"benchmark.md","\n".join(lines)+"\n")
    return report


def main():
    configure_console();parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("plan",type=Path);args=parser.parse_args()
    result=benchmark(args.plan,get_settings())
    print(result["benchmark_project"])


if __name__=="__main__": main()
