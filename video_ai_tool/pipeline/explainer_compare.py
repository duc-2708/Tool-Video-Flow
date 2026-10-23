"""Create a separate v2 script project and a readable old/new comparison."""
import argparse
import json
from pathlib import Path
import shutil
from config.settings import get_settings
from schemas.edit_plan import EditPlan
from schemas.research_brief import ResearchBrief
from pipeline.projects import create_project
from agents.director import run_director,director_diagnostics,director_provider
from agents.explainer_research import knowledge_notes
from agents.explainer_director import checkpoint_summary
from utils.atomic_io import write_json_atomic,write_text_atomic
from utils.console import configure_console


def compare(source,settings,*,duration=60,progress=print):
    source=Path(source).resolve()
    brief=ResearchBrief.model_validate_json((source/"brief.json").read_text(encoding="utf-8"))
    old=EditPlan.model_validate_json((source/"edit_plan.json").read_text(encoding="utf-8"))
    summary=checkpoint_summary(source/"director_state.json")
    if set(summary)!={"outline","written","humanized"}: raise ValueError("Cần checkpoint đủ outline/written/humanized để đối chiếu.")
    dest=create_project(settings.output_dir,"Explainer v2 Barclays" if "barclays" in brief.topic.casefold() else "Explainer v2 "+brief.topic)
    shutil.copy2(source/"director_state.json",dest/"director_state.legacy.json")
    shutil.copy2(source/"edit_plan.json",dest/"edit_plan.before.json")
    for name in ("sources.json","credits.txt"):
        if (source/name).is_file(): shutil.copy2(source/name,dest/name)
    diagnostics=director_diagnostics(settings)
    if not brief.knowledge_notes:
        provider=director_provider(settings,diagnostics)
        try: knowledge_notes(brief,provider,diagnostics)
        finally: provider.close()
    brief.content_mode="explainer_v2"
    write_json_atomic(dest/"brief.json",brief.model_dump(mode="json"))
    run_director(dest/"brief.json",settings,video_type=old.video_type or "news",video_format=old.format,duration_sec=duration,
        script_style="explain",content_mode="explainer_v2",style_preset=old.style_preset,progress=progress)
    new=EditPlan.model_validate_json((dest/"edit_plan.json").read_text(encoding="utf-8"))
    old_words=sum(len(s.narration.split()) for s in old.scenes);new_words=sum(len(s.narration.split()) for s in new.scenes)
    lines=["# So sánh Barclays: bản tin và Explainer v2",f"Nguồn checkpoint: {source}","",
        "| Chỉ số | Bản cũ | Explainer v2 |","|---|---:|---:|",f"| Cảnh/beat | {len(old.scenes)} | {len(new.scenes)} |",
        f"| Từ lời đọc | {old_words} | {new_words} |",f"| Thời lượng kế hoạch | {old.duration_sec:.1f}s | {new.duration_sec:.1f}s |","",
        "## Bản cũ",*(f"### Cảnh {s.id}\n{s.narration}\n" for s in old.scenes),"## Bản mới"]
    for scene in new.scenes:
        lines.extend([f"### Beat {scene.id} · {scene.information_kind}",f"Ý mới: {scene.new_information}",*(f"- **{s.type}** ({s.fact_ids}): {s.text}" for s in scene.sentences),""])
    if new.explainer_outline: lines.extend(["## Câu hỏi mở",new.explainer_outline.open_loop or "Đã bỏ câu hỏi chưa được trả lời.","Kết trả lời: "+new.explainer_outline.payoff])
    if new.script_critic: lines.extend(["## Critic (trước sửa)","```json",new.script_critic.model_dump_json(indent=2),"```"])
    lines.extend(["## Cảnh báo",*new.review_notes,"","Kiến thức nền là diễn giải có độ mềm, không phải fact sự kiện đã kiểm chứng. Không tạo audio/assets/render trong lần so sánh này."])
    write_text_atomic(dest/"comparison.md","\n\n".join(lines))
    return dest


def main():
    configure_console()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project",type=Path)
    parser.add_argument("--duration",type=float,default=60)
    args=parser.parse_args()
    try: settings=get_settings()
    except Exception:
        print("Cấu hình chưa hợp lệ; không in giá trị bí mật.");return 1
    try:
        dest=compare(args.project,settings,duration=args.duration)
        print("Đã lưu kịch bản: "+str(dest/"edit_plan.json"))
        print("So sánh: "+str(dest/"comparison.md"))
        return 0
    except Exception as error:
        diagnostics=director_diagnostics(settings);diagnostics.record_exception(error,"Explainer comparison")
        print("Chưa tạo xong Explainer: "+diagnostics.redact(str(error))[:1500]);return 1


if __name__=="__main__": raise SystemExit(main())
