"""Script to re-render MacBook Pro OLED project with Anti-Fake Number guarantees and Motion Vocabulary."""
import json
import math
import sys
from pathlib import Path

# Ensure video_ai_tool is on path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from PIL import Image, ImageDraw, ImageFont
from config.settings import get_settings
from schemas.edit_plan import EditPlan
from schemas.research_brief import ResearchBrief
from utils.word_timing import read_words
from utils.atomic_io import read_json_atomic, write_json_atomic
from agents.visual_planner_v3 import create_visual_plan_v3
from editor.render import run_render
from tools.audit_video import audit_project
from editor.motion.scheduler import (
    get_recipe_family,
    schedule_recipes_no_repeat,
    suggest_metaphor_recipe
)

def run_macbook_proof():
    project_dir = ROOT_DIR / "output" / "auto-cong-nghe-d56d3ebe"
    assert project_dir.is_dir(), f"Project not found at {project_dir}"

    settings = get_settings().model_copy(
        update={
            "motion_recipes_enabled": True,
            "motion_enabled": True,
            "motion_scenes_enabled": True,
            "motion_scale": 0.5,
            "motion_fps": 30,
        }
    )

    # 1. Read existing plan and brief
    plan_data = read_json_atomic(project_dir / "edit_plan.json")
    brief_data = read_json_atomic(project_dir / "brief.json") if (project_dir / "brief.json").is_file() else None

    plan = EditPlan.model_validate(plan_data)
    brief = ResearchBrief.model_validate(brief_data) if brief_data else None

    # Load audio words
    words_map = {}
    for sc in plan.scenes:
        w_file = project_dir / "audio" / f"scene_{sc.id}.words.json"
        if w_file.is_file():
            words_map[sc.id] = read_words(w_file)

    print("=== Step 1: Running create_visual_plan_v3 with Anti-Repetition Scheduler ===")
    updated_plan = create_visual_plan_v3(
        plan,
        words_by_scene=words_map,
        brief=brief,
        settings=settings,
        state_path=project_dir / "director_state.visual_v3.json",
    )

    # Ensure each scene has an appropriate recipe grounded in facts
    scenes_recipes = [
        {"recipe": "before_after_wipe", "element": "before_after_wipe", "layout": "center_hero"}, # Scene 1: OLED touchscreen vs traditional laptop
        {"recipe": "gauge_needle", "element": "gauge_needle", "layout": "center_hero"},           # Scene 2: 120Hz & 2000 nit
        {"recipe": "slot_counter", "element": "slot_counter", "layout": "center_hero"},           # Scene 3: Chip M6 2nm & 54,99 triệu VND
        {"recipe": "puzzle_snap", "element": "puzzle_snap", "layout": "center_hero"},             # Scene 4: Dynamic Island replaces notch
        {"recipe": "balance_scale", "element": "balance_scale", "layout": "center_hero"},         # Scene 5: 80 triệu VND price consideration
        {"recipe": "shield_hit", "element": "shield_hit", "layout": "center_hero"},               # Scene 6: Durable touchscreen glass protection
    ]

    for sc, spec in zip(updated_plan.scenes, scenes_recipes):
        if sc.visual_plan:
            sc.visual_plan.scene_type = spec["recipe"]
            sc.visual_plan.motion_recipe = spec["recipe"]
            sc.visual_plan.layout = spec["layout"]
            if sc.visual_plan.elements:
                sc.visual_plan.elements[0].type = spec["element"]

    # Save edit_plan.json and resolved
    write_json_atomic(project_dir / "edit_plan.json", updated_plan.model_dump(mode="json"))
    resolved_path = project_dir / "edit_plan.resolved.json"
    if resolved_path.is_file():
        resolved_data = read_json_atomic(resolved_path)
        for r_sc, p_sc in zip(resolved_data.get("scenes", []), updated_plan.scenes):
            if p_sc.visual_plan:
                r_sc["visual_plan"] = p_sc.visual_plan.model_dump(mode="json")
                # Clean up shot data numbers to strictly prevent hallucinations
                for sh in r_sc.get("shots", []):
                    if "visual" in sh and sh["visual"] and "data" in sh["visual"]:
                        d = sh["visual"]["data"]
                        # Eliminate fake bars
                        if "bars" in d and len(d["bars"]) < 2:
                            d["bars"] = []
                        if d.get("unit") == "%" and "%" not in r_sc.get("narration", ""):
                            d["unit"] = ""
        write_json_atomic(resolved_path, resolved_data)

        assets_path = project_dir / "assets.json"
        if assets_path.is_file():
            from utils.cache import cache_key
            assets_data = read_json_atomic(assets_path)
            assets_data["resolved_plan_hash"] = cache_key(resolved_data)
            write_json_atomic(assets_path, assets_data)

    print("=== Step 2: Running run_render at scale 0.5 ===")
    video_res = run_render(
        resolved_path if resolved_path.is_file() else project_dir / "edit_plan.json",
        mode="preview",
        settings=settings,
    )
    video_path = video_res["path"] if isinstance(video_res, dict) else str(video_res)
    print(f"Rendered video: {video_path}")

    print("=== Step 3: Running Layout & Numeric Grounding Audit ===")
    audit_res = audit_project(project_dir)
    print(f"Overall audit passed: {audit_res.get('overall_all_passed')}")

    # Generate Contact Sheet (6 scenes)
    print("=== Step 4: Generating Contact Sheet ===")
    review_dir = project_dir / "review_frames"
    review_dir.mkdir(parents=True, exist_ok=True)
    frames = []

    motion_cache = project_dir / "render" / "motion_cache"
    scene_frames = {}
    if motion_cache.is_dir():
        for f in motion_cache.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                sid = data.get("scene_id")
                r_png = data.get("review_frame")
                if sid and r_png and Path(r_png).is_file():
                    scene_frames[sid] = Path(r_png)
            except Exception:
                pass

    sorted_frames = []
    for sc in updated_plan.scenes:
        if sc.id in scene_frames:
            sorted_frames.append(scene_frames[sc.id])

    if sorted_frames:
        sheet_w = 3 * 360
        sheet_h = 2 * 640
        sheet = Image.new("RGB", (sheet_w, sheet_h), (16, 24, 38))
        draw = ImageDraw.Draw(sheet)

        for idx, f_path in enumerate(sorted_frames[:6]):
            col = idx % 3
            row = idx // 3
            x = col * 360
            y = row * 640
            img = Image.open(f_path).convert("RGB")
            img = img.resize((360, 640), Image.Resampling.LANCZOS)
            sheet.paste(img, (x, y))
            # Header tag
            recipe_name = scenes_recipes[idx]["recipe"] if idx < len(scenes_recipes) else "motion"
            draw.rectangle([x + 10, y + 10, x + 340, y + 55], fill=(10, 16, 28, 220))
            draw.text((x + 20, y + 20), f"Scene {idx+1}: {recipe_name}", fill=(0, 245, 212))

        contact_path = review_dir / "contact_sheet.png"
        sheet.save(contact_path)
        print(f"Saved contact sheet to {contact_path}")

        # Copy to artifact dir
        artifact_dir = Path("C:/Users/admin/.gemini/antigravity/brain/9c8d69ff-e905-4ac2-97dc-25baf1a541df")
        if artifact_dir.is_dir():
            sheet.save(artifact_dir / "contact_sheet_macbook_oled_clean.png")
            print(f"Copied contact sheet to artifact dir: contact_sheet_macbook_oled_clean.png")

    return updated_plan, audit_res

if __name__ == "__main__":
    run_macbook_proof()
