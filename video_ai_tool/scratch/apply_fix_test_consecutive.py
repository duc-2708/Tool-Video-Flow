with open('tests/test_scene_director.py', 'r', encoding='utf-8') as f:
    text = f.read()

with open('scratch/fix_test_consecutive.py', 'r', encoding='utf-8') as f:
    replacement = f.read()

target = '''def test_scene_director_no_consecutive_ai_clips(sample_edit_plan):
    scene_plan = ScenePlanResponse(
        scenes=[
            ScenePlanItem(scene_id=1, mode="motion", motion_brief=MotionBrief(recipe_candidates=["text_focus"])),
            ScenePlanItem(scene_id=2, mode="motion", motion_brief=MotionBrief(recipe_candidates=["text_focus"])),
            ScenePlanItem(scene_id=3, mode="motion", motion_brief=MotionBrief(recipe_candidates=["text_focus"])),
            ScenePlanItem(
                scene_id=4,
                mode="ai_clip",
                motion_brief=MotionBrief(recipe_candidates=["puzzle_snap"]),
                ai_clip=AiClipBrief(prompt_en="sleek display notch morphing", fallback_recipe="puzzle_snap")
            ),
            ScenePlanItem(
                scene_id=5,
                mode="hybrid", # Vi phạm: Liền kề cảnh 4 (ai_clip)
                motion_brief=MotionBrief(recipe_candidates=["balance_scale"]),
                ai_clip=AiClipBrief(prompt_en="glowing balance scale in darkness", fallback_recipe="balance_scale")
            ),
            ScenePlanItem(scene_id=6, mode="motion", motion_brief=MotionBrief(recipe_candidates=["shield_hit"])),
        ]
    )

    notes = validate_and_repair_scene_plan(scene_plan, sample_edit_plan, ai_clips_max=2)

    # Scene 5 must be demoted to motion
    assert scene_plan.scenes[3].mode == "ai_clip"
    assert scene_plan.scenes[4].mode == "motion"
    assert any("tránh 2 clip AI liền kề" in n for n in notes)'''

assert target in text, 'target not found'
text = text.replace(target, replacement, 1)

with open('tests/test_scene_director.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Updated test_scene_director.py')
