"""Offline 30s template showcase using an existing verified brief and audio.

Creates a separate project. Voice is reused; presentation pauses are explicit,
not a generated longer script. Does not call TTS, Gemini or stock providers.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import uuid
from imageio_ffmpeg import get_ffmpeg_exe
from config.settings import ROOT_DIR,Settings
from schemas.assets import ResolvedEditPlan
from schemas.research_brief import ResearchBrief
from schemas.visual import Visual,VisualData,VisualBar
from schemas.style import StyleRenderDefaults,CaptionStyle
from agents.visual_planner import visual_issues
from utils.atomic_io import write_json_atomic,write_text_atomic
from utils.console import configure_console
from utils.media import measured_audio_duration
from editor.render import run_render


def build_barclays_demo(source,output_root=None):
    source=Path(source).resolve()
    brief=ResearchBrief.model_validate_json((source/"brief.json").read_text(encoding="utf-8"))
    if "barclays" not in (brief.topic+" "+" ".join(f.claim for f in brief.facts)).casefold():
        raise ValueError("Mẫu này cần brief Barclays đã có, không tự tìm nguồn.")
    plan=ResolvedEditPlan.model_validate_json((source/"edit_plan.resolved.json").read_text(encoding="utf-8"))
    if len(plan.scenes)<3 or len(brief.facts)<7: raise ValueError("Demo cần ba cảnh audio và bảy fact Barclays hiện có.")
    dest=Path(output_root or ROOT_DIR/"output")/("barclays-templates-"+uuid.uuid4().hex[:8])
    (dest/"audio").mkdir(parents=True);(dest/"clips").mkdir()
    shutil.copy2(source/"brief.json",dest/"brief.json")
    plan.scenes=plan.scenes[:3]
    plan.content_timed=True;plan.title="Barclays và kế hoạch nhân sự";plan.format="tiktok"
    plan.source_plan_hash="offline-template-showcase"
    plan.render_style=StyleRenderDefaults(captions=CaptionStyle(appearance="pill"),progress_tracker=True,progress_labels=["Kế hoạch","Vai trò","Quy mô"])
    plan.music.volume=.08
    layouts=[
        [("hook_card",dict(text="Barclays cắt 5.000 việc làm",highlight=["5.000","việc","làm"],fact_ids=[1])),
         ("stat_card",dict(value=5000,label="Kế hoạch cắt giảm nhân sự",unit="việc làm",source=brief.facts[0].source_name,fact_ids=[1])),
         ("source_card",dict(source=brief.facts[0].source_name,date=brief.facts[0].published_at or "",title="Kế hoạch nhân sự Barclays",source_url=str(brief.facts[0].source_url),fact_ids=[1]))],
        [("steps_list",dict(items=["Khoảng 1.000 vị trí đã cắt giảm","4.000 vị trí tiếp theo trước cuối năm"],fact_ids=[1,4])),
         ("compare_bars",dict(bars=[VisualBar(label="Đã cắt giảm",value=1000,unit=" vị trí",fact_id=1),VisualBar(label="Tiếp theo",value=4000,unit=" vị trí",fact_id=1)],fact_ids=[1,4])),
         ("stat_card",dict(value=60,unit="%",label="Các vai trò hỗ trợ",source=brief.facts[1].source_name,fact_ids=[2]))],
        [("text_focus",dict(text="Khoảng 5% tổng số nhân viên",highlight=["5%"],fact_ids=[3])),
         ("stat_card",dict(value=5,unit="%",label="Tổng số nhân viên toàn tập đoàn",source=brief.facts[2].source_name,fact_ids=[3])),
         ("source_card",dict(source=brief.facts[2].source_name,date=brief.facts[2].published_at or "",title="Kế hoạch nhân sự Barclays",source_url=str(brief.facts[2].source_url),fact_ids=[3]))]]
    for i,scene in enumerate(plan.scenes):
        original_audio=source/"audio"/f"scene_{scene.id}.mp3"
        length=measured_audio_duration(original_audio)
        if length>10: raise ValueError("Audio dài hơn phần demo; không cắt mất lời đọc.")
        audio=dest/"audio"/f"scene_{scene.id}.mp3"
        subprocess.run([get_ffmpeg_exe(),"-hide_banner","-loglevel","error","-y","-i",str(original_audio),"-af","apad","-t","10","-c:a","libmp3lame",str(audio)],check=True,capture_output=True,timeout=60)
        # Accurate timing for the original voice; silence at the end has no captions.
        from editor.captions import word_timings
        timing=original_audio.with_suffix(".words.json")
        words=word_timings(scene.narration,length,timing)
        write_json_atomic(audio.with_suffix(".words.json"),[{"text":w,"start":a,"end":b} for w,a,b in words])
        first=scene.shots[0]
        scene.fact_ids=sorted({f for _,data in layouts[i] for f in data["fact_ids"]})
        scene.shots=[]
        for name,data in layouts[i]:
            shot=first.model_copy(deep=True)
            shot.duration_sec=10/3;shot.type="text_card";shot.text_overlay=None;shot.effect="none"
            shot.visual=Visual(template=name,data=VisualData(**data))
            scene.shots.append(shot)
        scene.transition_out="fade"
    issues=visual_issues(plan,brief)
    if issues: raise ValueError(str(issues))
    plan.target_duration_sec=30.;plan.requested_duration_sec=30.
    plan.warnings=["Demo 30 giây: tái sử dụng ~20 giây giọng đọc đã có, phần còn lại là khoảng nghỉ xem đồ họa; không tạo thêm lời đọc bằng API."]
    write_json_atomic(dest/"edit_plan.resolved.json",plan.model_dump(mode="json"))
    credits=(source/"credits.txt").read_text(encoding="utf-8") if (source/"credits.txt").is_file() else ""
    write_text_atomic(dest/"credits.txt",credits+"\nDemo: chỉ đồ họa Pillow, audio tái sử dụng; không tải thêm stock/video.\n")
    write_text_atomic(dest/"report.md","# Barclays: bản thử mẫu đồ họa\n\n"+plan.warnings[0]+"\n\nNguồn: "+str(source)+"\n")
    return dest/"edit_plan.resolved.json"


def main():
    configure_console()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project",type=Path)
    args=parser.parse_args()
    path=build_barclays_demo(args.project)
    last=[-1]
    def progress(value,message):
        n=int(value*100)
        if n>=last[0]+10 or n==100:
            print(f"{n}% · {message}",flush=True);last[0]=n
    result=run_render(path,settings=Settings(root_dir=ROOT_DIR),progress=progress)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__": main()
