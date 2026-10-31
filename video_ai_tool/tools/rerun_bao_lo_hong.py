import json
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

# Add video_ai_tool root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config.settings import get_settings
from editor.motion.scheduler import schedule_shots_no_repeat, AVAILABLE_SHOT_RECIPES
from pipeline.render_motion import render_scene
from schemas.edit_plan import EditPlan
from schemas.motion_scene import MotionScenePlan
from schemas.visual import VisualBeat, VisualData
from utils.atomic_io import read_json_atomic, write_json_atomic

def main():
    settings = get_settings()
    project_dir = BASE_DIR / "output" / "auto-cong-nghe-e97dccbd"
    if not project_dir.exists():
        project_dir = Path("video_ai_tool/output/auto-cong-nghe-e97dccbd")
    plan_file = project_dir / "edit_plan.json"
    resolved_file = project_dir / "edit_plan.resolved.json"
    
    assert plan_file.is_file(), f"File {plan_file} not found"
    plan_data = read_json_atomic(plan_file)
    plan = EditPlan.model_validate(plan_data)
    
    resolved_data = read_json_atomic(resolved_file) if resolved_file.is_file() else plan_data

    print(f"=== PROJECT: {project_dir.name} ===")
    print(f"Title: {plan.title}")
    print(f"Total scenes: {len(plan.scenes)}")

    # 1. Collect all shots across video with precise per-shot spoken audio slice
    all_shots_data = []
    shot_map = []
    for s_idx, scene in enumerate(plan.scenes):
        is_recap = (s_idx == len(plan.scenes) - 1)
        res_scene = resolved_data.get("scenes", [])[s_idx] if s_idx < len(resolved_data.get("scenes", [])) else {}
        sc_dur = res_scene.get("duration_sec") or 10.0
        
        # Audio words
        words_file = project_dir / "audio" / f"scene_{scene.id}.words.json"
        words_list = []
        if words_file.is_file():
            wdata = read_json_atomic(words_file)
            words_list = wdata.get("words", [])

        res_shots = res_scene.get("shots", [])
        num_shots = len(scene.shots)
        cur_time = 0.0

        for sh_idx, shot in enumerate(scene.shots):
            sh_dur = res_shots[sh_idx].get("duration_sec") if sh_idx < len(res_shots) else (sc_dur / num_shots)
            s_time = cur_time
            e_time = cur_time + sh_dur
            cur_time = e_time

            shot_spoken_words = [
                w["text"] for w in words_list
                if (w["start"] + w["end"]) / 2 >= s_time and (w["start"] + w["end"]) / 2 < e_time
            ]
            spoken_slice = " ".join(shot_spoken_words).strip()

            c_text = shot.card_text
            if not c_text:
                if s_idx == 4 and sh_idx == 4:
                    c_text = "Nâng cấp phòng thủ"
                elif spoken_slice:
                    c_text = spoken_slice
                else:
                    c_text = scene.narration

            # Make sure shot text is strictly grounded in spoken slice or card_text
            shot_narration = spoken_slice if spoken_slice else c_text
            
            all_shots_data.append({
                "card_text": c_text,
                "text": c_text,
                "narration": shot_narration,
                "scene_narration": scene.narration,
                "is_recap": is_recap,
                "duration": sh_dur,
                "duration_sec": sh_dur,
                "scene_id": scene.id,
                "shot_id": sh_idx + 1,
            })
            shot_map.append((s_idx, sh_idx))

    print(f"Total shots across video: {len(all_shots_data)}")

    # 2. Schedule shots adhering strictly to max_freq <= 2, min_dist >= 4
    scheduled_shots, notes = schedule_shots_no_repeat(
        all_shots_data,
        min_distinct=min(12, len(all_shots_data)),
        min_dist=4,
        max_freq=2
    )

    print("\n--- SCHEDULED SHOTS ---")
    recipe_counts = Counter()
    for idx, sh in enumerate(scheduled_shots):
        r = sh["recipe"]
        recipe_counts[r] += 1
        d = sh["data"]
        lbl = d.get("label") or d.get("text") or ""
        val = d.get("value")
        unit = d.get("unit") or ""
        print(f"Shot {idx+1:>2} [Scene {sh['scene_id']} - Shot {sh['shot_id']}]: recipe={r:<24} | val={str(val):<5} | unit={unit:<3} | lbl='{lbl}'")

    print("\nRecipe usage frequency:")
    for r, c in recipe_counts.most_common():
        print(f"  {r}: {c} times")
        assert c <= 2, f"VIOLATION: Recipe {r} used {c} > 2 times!"

    # 3. Apply scheduled visual_plan to plan.scenes and resolved_data
    for sh_data, (s_idx, sh_idx) in zip(scheduled_shots, shot_map):
        scene = plan.scenes[s_idx]
        shot = scene.shots[sh_idx]
        r = sh_data["recipe"]
        d = sh_data["data"]
        
        v_beats = [
            VisualBeat(at_sec=b["at_sec"], action=b["action"])
            for b in sh_data.get("beats", [])
        ]
        
        valid_keys = set(VisualData.model_fields.keys())
        clean_d = {k: v for k, v in d.items() if k in valid_keys}
        shot_vdata = VisualData(**clean_d)
        
        shot.visual_plan = MotionScenePlan(
            scene_type=r,
            layout="center_hero",
            theme="neon_dark",
            data=shot_vdata,
            beats=v_beats,
        )
        # Also set primary recipe for scene if first shot
        if sh_idx == 0:
            scene.visual_plan = MotionScenePlan(
                scene_type=r,
                layout="center_hero",
                theme="neon_dark",
                data=shot_vdata,
                beats=v_beats,
            )

        # Update resolved_data
        if s_idx < len(resolved_data.get("scenes", [])):
            res_sc = resolved_data["scenes"][s_idx]
            if sh_idx < len(res_sc.get("shots", [])):
                res_sc["shots"][sh_idx]["visual_plan"] = shot.visual_plan.model_dump(mode="json")
                res_sc["shots"][sh_idx]["card_text"] = sh_data.get("card_text") or shot.card_text
            if sh_idx == 0:
                res_sc["visual_plan"] = scene.visual_plan.model_dump(mode="json")

    # Write updated resolved plan
    write_json_atomic(resolved_file, resolved_data)
    print("\nSuccessfully updated edit_plan.resolved.json with scheduled recipes!")

if __name__ == "__main__":
    main()
