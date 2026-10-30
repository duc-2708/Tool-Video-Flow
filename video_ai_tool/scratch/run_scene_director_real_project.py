import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from schemas.edit_plan import EditPlan
from schemas.research_brief import ResearchBrief
from config.settings import get_settings
from agents.scene_director import run_scene_director
from agents.visual_planner_v3 import create_visual_plan_v3

def main():
    project_dir = ROOT / "output" / "auto-cong-nghe-d56d3ebe"
    plan_path = project_dir / "edit_plan.json"
    brief_path = project_dir / "brief.json"

    plan = EditPlan.model_validate(json.loads(plan_path.read_text(encoding="utf-8")))
    brief = ResearchBrief.model_validate(json.loads(brief_path.read_text(encoding="utf-8"))) if brief_path.is_file() else None
    settings = get_settings().model_copy(update={"ai_clips_max_per_video": 2, "scene_director_enabled": True})

    print(f"=== Chạy Scene Director cho dự án: {project_dir.name} ===")
    scene_plan = run_scene_director(project_dir, plan, settings=settings, brief=brief)

    out_file = project_dir / "scene_plan.json"
    print(f"-> Đã lưu scene_plan.json tại: {out_file} (kích thước: {out_file.stat().st_size} bytes)")

    print("\n--- BẢNG KẾ HOẠCH CẢNH (SCENE PLAN) ---")
    for sc in scene_plan.scenes:
        print(f"\n[CẢNH {sc.scene_id}] Mode: {sc.mode.upper()}")
        print(f"  - Lý do: {sc.rationale}")
        print(f"  - Ý tưởng hình: {sc.motion_brief.visual_idea}")
        print(f"  - Recipe đề xuất: {', '.join(sc.motion_brief.recipe_candidates)}")
        print(f"  - Key beats: {len(sc.motion_brief.key_beats)} beats")
        for b in sc.motion_brief.key_beats:
            print(f"      * '{b.at_phrase}' -> {b.event}")
        if sc.emphasis:
            print(f"  - Emphasis: {[f'{e.text} ({e.effect}, {e.place})' for e in sc.emphasis]}")
        if sc.ai_clip:
            print(f"  - AI Clip:")
            print(f"      * Prompt EN: {sc.ai_clip.prompt_en}")
            print(f"      * Camera: {sc.ai_clip.camera}")
            print(f"      * Fallback Recipe: {sc.ai_clip.fallback_recipe}")

    print("\n--- REVIEW NOTES & VALIDATION ---")
    for n in scene_plan.review_notes:
        print(f"  * {n}")

    # Kiểm tra hợp nhất với Visual Planner:
    print("\n=== Kiểm tra hợp nhất Scene Director với Visual Planner ===")
    from agents.visual_planner_v3 import render_visual_prompt, find_prompt_path, REGISTRY
    prompt_tpl = find_prompt_path("visual_planner.md", settings).read_text(encoding="utf-8")
    rendered_visual_prompt = render_visual_prompt(prompt_tpl, plan, brief, REGISTRY, scene_plan=scene_plan)
    print("-> Visual Planner prompt đã nhúng Scene Director Motion Brief thành công!")
    # In đoạn trích cảnh 1 và cảnh 2 từ prompt đã render
    p_lines = rendered_visual_prompt.splitlines()
    for l in p_lines:
        if "Scene Director" in l or "Recipe đề xuất" in l or "CẢNH 1" in l or "CẢNH 2" in l:
            print(f"   {l}")

if __name__ == "__main__":
    main()
