with open('agents/visual_planner_v3.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update render_visual_prompt signature and logic
old_fn_start = '''def render_visual_prompt(
    template_text: str,
    plan: EditPlan,
    brief: ResearchBrief | None = None,
    registry: ElementRegistry = REGISTRY,
) -> str:
    """Fill dynamic registry catalog and formatted script scenes into Prompt B."""
    total_sec = sum(getattr(s, "duration_sec", 0.0) or 8.0 for s in plan.scenes)
    if total_sec <= 0:
        total_sec = plan.duration_sec or 45.0
    sec = int(total_sec)
    scene_count = len(plan.scenes)

    script_lines: list[str] = []
    for sc in plan.scenes:
        facts_str = f" [Facts: {', '.join(str(f) for f in sc.fact_ids)}]" if sc.fact_ids else ""
        role_str = getattr(sc, "role", "explain")
        script_lines.append(f"CẢNH {sc.id} ({role_str}){facts_str}:")
        script_lines.append(f"Lời đọc: {sc.narration}")
        script_lines.append("")'''

new_fn_start = '''def render_visual_prompt(
    template_text: str,
    plan: EditPlan,
    brief: ResearchBrief | None = None,
    registry: ElementRegistry = REGISTRY,
    scene_plan: Any | None = None,
) -> str:
    """Fill dynamic registry catalog, Scene Director briefs, and formatted script scenes into Prompt B."""
    total_sec = sum(getattr(s, "duration_sec", 0.0) or 8.0 for s in plan.scenes)
    if total_sec <= 0:
        total_sec = plan.duration_sec or 45.0
    sec = int(total_sec)
    scene_count = len(plan.scenes)

    script_lines: list[str] = []
    for sc in plan.scenes:
        facts_str = f" [Facts: {', '.join(str(f) for f in sc.fact_ids)}]" if sc.fact_ids else ""
        role_str = getattr(sc, "role", "explain")
        script_lines.append(f"CẢNH {sc.id} ({role_str}){facts_str}:")
        script_lines.append(f"Lời đọc: {sc.narration}")
        if scene_plan:
            sp_item = next((it for it in getattr(scene_plan, "scenes", []) if it.scene_id == sc.id), None)
            if sp_item:
                mb = getattr(sp_item, "motion_brief", None)
                if mb:
                    script_lines.append("  [Scene Director Motion Brief]:")
                    script_lines.append(f"    - Chế độ (mode): {sp_item.mode}")
                    if getattr(mb, "visual_idea", ""):
                        script_lines.append(f"    - Ý tưởng hình: {mb.visual_idea}")
                    if getattr(mb, "recipe_candidates", []):
                        script_lines.append(f"    - Recipe đề xuất (BẮT BUỘC xem xét): {', '.join(mb.recipe_candidates)}")
                    if getattr(mb, "key_beats", []):
                        beats_str = "; ".join(f"'{b.at_phrase}' -> {b.event}" for b in mb.key_beats)
                        script_lines.append(f"    - Key beats: {beats_str}")
        script_lines.append("")'''

assert old_fn_start in text, 'old_fn_start not found'
text = text.replace(old_fn_start, new_fn_start, 1)

# 2. Update create_visual_plan_v3 signature
old_sig = '''def create_visual_plan_v3(
    plan: EditPlan,
    words_by_scene: dict[int, list[dict[str, Any]]] | None = None,
    brief: ResearchBrief | None = None,
    provider: Any = None,
    settings: Settings | None = None,
    diagnostics: Diagnostics | None = None,
    progress: Callable[[str], None] | None = None,
    state_path: Path | None = None,
) -> EditPlan:'''

new_sig = '''def create_visual_plan_v3(
    plan: EditPlan,
    words_by_scene: dict[int, list[dict[str, Any]]] | None = None,
    brief: ResearchBrief | None = None,
    provider: Any = None,
    settings: Settings | None = None,
    diagnostics: Diagnostics | None = None,
    progress: Callable[[str], None] | None = None,
    state_path: Path | None = None,
    **kwargs: Any,
) -> EditPlan:'''

assert old_sig in text, 'old_sig not found'
text = text.replace(old_sig, new_sig, 1)

# 3. Update create_visual_plan_v3 to load scene_plan if available
old_create_start = '''    rendered_prompt = render_visual_prompt(template_text, plan, brief, REGISTRY)'''

new_create_start = '''    # Load scene_plan.json if available
    scene_plan = kwargs.get("scene_plan")
    if not scene_plan and state_path:
        sp_candidate = Path(state_path).parent / "scene_plan.json"
        if sp_candidate.is_file():
            try:
                from schemas.scene_director import ScenePlanResponse
                scene_plan = ScenePlanResponse.model_validate_json(sp_candidate.read_text(encoding="utf-8"))
            except Exception:
                pass

    rendered_prompt = render_visual_prompt(template_text, plan, brief, REGISTRY, scene_plan=scene_plan)'''

assert old_create_start in text, 'old_create_start not found'
text = text.replace(old_create_start, new_create_start, 1)

with open('agents/visual_planner_v3.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Successfully integrated scene_plan into agents/visual_planner_v3.py')
