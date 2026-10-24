"""Rebuild the supplied job-guarantee regression in a NEW project; no LLM calls."""
import argparse
from copy import deepcopy
import hashlib
import re
from pathlib import Path
import shutil

from agents.director import validate_plan,DirectorRequest
from agents.presentation import humanize_locally,repair_generic_hook,source_card_once,normalize_cards
from agents.explainer_visuals import build_v2_shots
from agents.explainer_guard import sync_narration
from config.settings import get_settings
from editor.render import run_render
from pipeline.assets import run_assets
from pipeline.projects import create_project
from schemas.edit_plan import EditPlan
from schemas.explainer import ScriptSentence
from schemas.research_brief import ResearchBrief
from utils.atomic_io import write_json_atomic,write_text_atomic
from utils.console import configure_console
from utils.diagnostics import Diagnostics


def revised_plan(plan,brief):
    plan=plan.model_copy(deep=True)
    humanize_locally(plan,brief);repair_generic_hook(plan,brief)
    # This editorial regression is tied to the provided topic, never a global
    # canned script or a source of facts for unrelated future projects.
    if "job guarantee" in brief.topic.casefold() or "bảo đảm việc làm" in brief.topic.casefold():
        replacements={
            3:"Thay đổi tác vụ chưa đồng nghĩa mất cả nghề. Công việc tạm thời tạo khoảng nghỉ để học kỹ năng mới và chuyển hướng.",
            5:"Hãy hình dung một chiếc ghế dự phòng. Người mất việc tham gia sửa công trình địa phương, giữ kỹ năng và nhịp làm việc trong lúc tìm hướng mới.",
            6:"Bảo đảm việc làm là lưới đệm, không phải lời giải trọn gói. Theo mình, hiệu quả phụ thuộc vào ngân sách, công việc hữu ích và năng lực quản lý."}
        # These are paraphrases of the existing background notes/analogy, with
        # no new quantities, names, quotes or promises about a concrete event.
        if not brief.knowledge_notes: replacements={}
        for scene in plan.scenes:
            if scene.id in replacements and not any(s.type=="event" for s in scene.sentences):
                kind="opinion" if scene.id==6 else "explain"
                scene.sentences=[ScriptSentence(type=kind,text=replacements[scene.id])]
            for sentence in scene.sentences:
                sentence.text=re.sub(r"đó là rủi ro, không phải kết cục có thể\.","Đó là rủi ro, không phải kết cục đã định.",sentence.text,flags=re.I)
    sync_narration(plan)
    for scene in plan.scenes:
        for shot in scene.shots: shot.card_text=None;shot.emphasis=[]
    build_v2_shots(plan,brief);source_card_once(plan,brief);normalize_cards(plan,brief)
    request=DirectorRequest(video_type=plan.video_type or "news",video_format=plan.format,
        duration_sec=max(6,plan.requested_duration_sec or plan.duration_sec),content_mode=plan.content_mode)
    return validate_plan(plan,brief,request,check_style=False,allow_merge=False)


def run_review(source,settings,*,progress=None):
    source=Path(source).resolve()
    files=[p for folder in (source,source/"audio",source/"clips") for p in folder.iterdir() if p.is_file() and p.suffix in {".json",".mp3",".mp4",".png",".jpg",".txt"}]
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    plan=EditPlan.model_validate_json((source/"edit_plan.json").read_text(encoding="utf-8"))
    brief=ResearchBrief.model_validate_json((source/"brief.json").read_text(encoding="utf-8"))
    revised=revised_plan(plan,brief)
    project=create_project(settings.output_dir,revised.title+"-review")
    for name in ("brief.json","sources.json"):
        if (source/name).is_file(): shutil.copyfile(source/name,project/name)
    write_json_atomic(project/"edit_plan.json",revised.model_dump(mode="json"))
    write_text_atomic(project/"editorial_review.md","# Bản sửa trình bày\n\nNguồn gốc: "+str(source)+
        "\n\nBản mới dùng cùng brief. Không gọi LLM/stock/AI clip. TTS Edge tạo lại theo lời đọc đã sửa. "
        "Cảnh 3/5/6 diễn đạt lại kiến thức nền/ẩn dụ có sẵn; không phải dữ kiện sự kiện mới.\n")
    run_assets(project/"edit_plan.json",settings,providers=[],progress=lambda i,n,m:print(m,flush=True))
    render_settings=settings.model_copy(update={"render_width":1080,"render_height":1920,"motion_scale":1.})
    result=run_render(project/"edit_plan.resolved.json",mode="final",settings=render_settings,progress=progress)
    from editor.runtime import VideoFileClip
    from PIL import Image
    review=settings.output_dir/"review_frames";review.mkdir(exist_ok=True)
    from editor.timeline import build_timeline
    timeline=build_timeline(project/"edit_plan.resolved.json")
    frames=[]
    with VideoFileClip(result["path"],audio=False) as clip:
        for scene in timeline.scenes:
            t=min(result["duration_sec"]-.1,scene.start+min(1.7,scene.duration*.5))
            path=review/f"{project.name}_scene_{scene.spec.id}.png"
            Image.fromarray(clip.get_frame(t)).save(path);frames.append(str(path))
        source_shot=timeline.scenes[-1].shots[-1]
        t=min(clip.duration-.1,source_shot.start+min(.8,source_shot.duration*.5))
        path=review/f"{project.name}_source_final.png"
        Image.fromarray(clip.get_frame(t)).save(path);frames.append(str(path))
    evidence={"original_project":str(source),"review_project":str(project),"render":result,"frames":frames,
        "original_inputs_unchanged":all(Path(p).is_file() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in before.items()),
        "input_files_checked":len(before),"llm_calls":0,"ai_clip_calls":0}
    write_json_atomic(project/"presentation_review.json",evidence)
    write_json_atomic(review/(project.name+".json"),evidence)
    return evidence


def main():
    configure_console();p=argparse.ArgumentParser(description=__doc__);p.add_argument("project",type=Path)
    args=p.parse_args();settings=get_settings()
    last=[0.]
    def progress(value,message):
        import time
        if time.monotonic()-last[0]>3 or value==1:
            print(f"{value:.0%} {message}",flush=True);last[0]=time.monotonic()
    result=run_review(args.project,settings,progress=progress)
    print(result["render"]["path"]);print("Original inputs unchanged:",result["original_inputs_unchanged"])


if __name__=="__main__": main()
