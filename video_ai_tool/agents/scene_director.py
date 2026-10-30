"""Scene Director (Phase 8): Intelligent scene staging decisions (motion vs ai_clip vs hybrid).
Assigns presentation mode per scene, generates motion briefs, and prompts AI video clips with strict guardrails.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Optional

from config.settings import Settings, get_settings
from schemas.edit_plan import EditPlan
from schemas.research_brief import ResearchBrief
from schemas.scene_director import (
    ScenePlanResponse,
    ScenePlanItem,
    MotionBrief,
    KeyBeatBrief,
    EmphasisItem,
    AiClipBrief,
)
from utils.atomic_io import read_json_atomic, write_json_atomic
from utils.diagnostics import Diagnostics
from agents.visual_diversity import values_in
from editor.motion.scheduler import suggest_metaphor_recipe


PROMPT_FILE = "scene_director.md"

# Forbidden keywords in AI clip prompts (no text, numbers, logos, real people, brands)
FORBIDDEN_PROMPT_PATTERNS = [
    (r"\b(?:text|words?|letters?|subtitles?|typography|alphabet)\b", ""),
    (r"\b(?:numbers?|digits?)\b", ""),
    (r"\b(?:logos?|brands?|watermarks?|signboards?|billboards?)\b", ""),
    (r"\b(?:apple)\b", "a premium tech maker"),
    (r"\b(?:iphone)\b", "a modern smartphone"),
    (r"\b(?:macbook)\b", "a sleek laptop"),
    (r"\b(?:ipad)\b", "a digital tablet"),
    (r"\b(?:samsung)\b", "an electronics maker"),
    (r"\b(?:nvidia)\b", "a semiconductor chipmaker"),
    (r"\b(?:tesla)\b", "an electric vehicle maker"),
    (r"\b(?:openai)\b", "an AI research lab"),
    (r"\b(?:elon\s+musk)\b", "a tech executive"),
    (r"\b(?:tim\s+cook)\b", "a corporate leader"),
    (r"\b(?:mark\s+zuckerberg)\b", "a social media founder"),
    (r"\b(?:donald\s+trump|joe\s+biden)\b", "a political figure"),
]


def load_scene_director_prompt_template(settings: Settings) -> str:
    """Load scene_director.md prompt template."""
    candidates = [
        settings.prompts_dir / PROMPT_FILE,
        Path(__file__).resolve().parents[1] / "prompts" / PROMPT_FILE,
    ]
    for p in candidates:
        if p.is_file():
            return p.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Không tìm thấy file prompt '{PROMPT_FILE}'.")


def build_script_summary(plan: EditPlan) -> str:
    """Format script scenes into input for Scene Director prompt."""
    lines: list[str] = []
    for sc in plan.scenes:
        role = getattr(sc, "role", "explain")
        dur = round(getattr(sc, "duration_sec", 0.0) or (len(sc.narration.split()) / 2.8), 1)
        word_count = len(sc.narration.split())
        lines.append(f"CẢNH {sc.id} ({role}, ~{dur}s, {word_count} từ):")
        lines.append(f"Lời đọc: \"{sc.narration}\"")
        if getattr(sc, "fact_ids", None):
            lines.append(f"Facts liên quan: {', '.join(str(fid) for fid in sc.fact_ids)}")
        lines.append("")
    return "\n".join(lines)


def build_scene_director_prompt(plan: EditPlan, ai_clips_max: int = 2, settings: Optional[Settings] = None) -> str:
    """Fill AI_CLIPS_MAX and script summary into scene_director.md."""
    settings = settings or get_settings()
    template = load_scene_director_prompt_template(settings)
    script_summary = build_script_summary(plan)
    rendered = template.replace("{AI_CLIPS_MAX}", str(ai_clips_max))
    rendered = rendered.replace("<<<DÁN KỊCH BẢN VÀO ĐÂY>>>", script_summary)
    return rendered


def clean_prompt_en(prompt_en: str) -> tuple[str, list[str]]:
    """Sanitize prompt_en to strictly remove text, numbers, logos, real people, brands."""
    cleaned = prompt_en
    replacements: list[str] = []
    for pat, repl in FORBIDDEN_PROMPT_PATTERNS:
        if re.search(pat, cleaned, re.I):
            matched = re.findall(pat, cleaned, re.I)
            replacements.append(f"thay '{', '.join(set(matched))}' -> '{repl}'")
            cleaned = re.sub(pat, repl, cleaned, flags=re.I)

    # Clean double spaces or dangling punctuation
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\s+([,.;])", r"\1", cleaned)
    return cleaned, replacements


def validate_and_repair_scene_plan(
    scene_plan: ScenePlanResponse,
    plan: EditPlan,
    ai_clips_max: int = 2,
    brief: Optional[ResearchBrief] = None,
) -> list[str]:
    """Validate and enforce Scene Director rules:
    1. ai_clip + hybrid <= 30% số cảnh và <= ai_clips_max.
    2. Không 2 clip AI liền kề.
    3. Cảnh có số liệu làm chủ thể -> ép về motion.
    4. prompt_en không chứa chữ/số/logo/tên người thật/thương hiệu.
    5. Thiếu fallback_recipe -> tự gán.
    """
    notes: list[str] = []
    total_scenes = len(scene_plan.scenes)
    max_allowed = min(ai_clips_max, max(1, math.floor(total_scenes * 0.30)))

    # Ensure all scenes from edit_plan exist in scene_plan
    plan_scene_map = {s.id: s for s in plan.scenes}

    # 1. Check numeric focus per scene (ép về motion nếu số liệu là chủ thể)
    for item in scene_plan.scenes:
        sc = plan_scene_map.get(item.scene_id)
        if not sc:
            continue
        narr = sc.narration
        has_stats = bool(re.search(r"\b\d+(?:[.,]\d+)*(?:\s*(?:%|tỷ|triệu|nghìn|ngàn|usd|vnd|nm|hz|nit|tb|gb))\b", narr, re.I))
        # If numbers are central subject and scene mode is ai_clip or hybrid
        if has_stats and item.mode in ("ai_clip", "hybrid"):
            # Check if narration is heavily statistical
            stat_tokens = values_in(narr)
            if len(stat_tokens) >= 1:
                old_mode = item.mode
                item.mode = "motion"
                notes.append(
                    f"[scene_director, nhóm 2] Cảnh {item.scene_id}: chứa số liệu chủ thể ({stat_tokens}); "
                    f"chuyển từ {old_mode} sang motion để đảm bảo căn cứ."
                )

    # 2. Check consecutive AI clips (không 2 clip AI liền kề)
    for i in range(len(scene_plan.scenes) - 1):
        curr = scene_plan.scenes[i]
        nxt = scene_plan.scenes[i + 1]
        if curr.mode in ("ai_clip", "hybrid") and nxt.mode in ("ai_clip", "hybrid"):
            old_mode = nxt.mode
            nxt.mode = "motion"
            notes.append(
                f"[scene_director, nhóm 2] Cảnh {nxt.scene_id}: tránh 2 clip AI liền kề ({curr.scene_id} và {nxt.scene_id}); "
                f"hạ cảnh {nxt.scene_id} ({old_mode}) về motion."
            )

    # 3. Check overall AI ratio (ai_clip + hybrid <= 30% và <= max_allowed)
    ai_scenes = [it for it in scene_plan.scenes if it.mode in ("ai_clip", "hybrid")]
    if len(ai_scenes) > max_allowed:
        # Keep highest priority scenes (e.g. hook id=1, or climax mid-video), demote the rest
        # Prioritize keeping hook if present, then lowest index
        ai_scenes_sorted = sorted(ai_scenes, key=lambda s: (0 if s.scene_id == 1 else 1, s.scene_id))
        keep_scenes = ai_scenes_sorted[:max_allowed]
        demote_scenes = ai_scenes_sorted[max_allowed:]
        for it in demote_scenes:
            old_mode = it.mode
            it.mode = "motion"
            notes.append(
                f"[scene_director, nhóm 2] Cảnh {it.scene_id}: vượt hạn mức AI clip ({len(ai_scenes)} > {max_allowed}); "
                f"chuyển {old_mode} sang motion dùng recipe {it.ai_clip.fallback_recipe if it.ai_clip else 'text_focus'}."
            )

    # 4. Prompt sanitization & fallback recipe validation
    for item in scene_plan.scenes:
        sc = plan_scene_map.get(item.scene_id)
        narr = sc.narration if sc else ""

        # Ensure motion_brief has recipe candidates
        if not item.motion_brief.recipe_candidates:
            suggested = suggest_metaphor_recipe(narr, item.scene_id)
            item.motion_brief.recipe_candidates = [suggested]

        # Ensure fallback_recipe
        if item.mode in ("ai_clip", "hybrid"):
            if not item.ai_clip:
                item.ai_clip = AiClipBrief(
                    prompt_en=f"A visually engaging cinematic sequence depicting {narr[:50]}",
                    fallback_recipe=item.motion_brief.recipe_candidates[0]
                )
                notes.append(f"[scene_director, nhóm 2] Cảnh {item.scene_id}: bổ sung ai_clip brief mặc định.")
            elif not item.ai_clip.fallback_recipe or item.ai_clip.fallback_recipe == "text_focus":
                item.ai_clip.fallback_recipe = item.motion_brief.recipe_candidates[0]
                notes.append(f"[scene_director, nhóm 2] Cảnh {item.scene_id}: tự gán fallback_recipe='{item.ai_clip.fallback_recipe}'.")

            # Clean forbidden words in prompt_en
            cleaned_p, reps = clean_prompt_en(item.ai_clip.prompt_en)
            if reps:
                item.ai_clip.prompt_en = cleaned_p
                notes.append(f"[scene_director, nhóm 2] Cảnh {item.scene_id}: lọc từ khóa cấm trong prompt_en ({'; '.join(reps)}).")

        # Ensure key_beats count >= 3 for motion/hybrid
        if item.mode in ("motion", "hybrid") and len(item.motion_brief.key_beats) < 3:
            words = narr.split()
            w_len = len(words)
            while len(item.motion_brief.key_beats) < 3:
                idx = len(item.motion_brief.key_beats)
                pos = min(w_len - 1, int(idx * (w_len / 3)))
                phrase = " ".join(words[pos:pos + 3])
                item.motion_brief.key_beats.append(
                    KeyBeatBrief(at_phrase=phrase, event=f"Diễn biến nhịp {idx + 1}")
                )

    scene_plan.review_notes.extend(notes)
    return notes


def generate_heuristic_scene_plan(plan: EditPlan, ai_clips_max: int = 2) -> ScenePlanResponse:
    """Deterministic fallback scene plan when LLM is unavailable or offline."""
    scenes: list[ScenePlanItem] = []
    total_scenes = len(plan.scenes)
    max_allowed = min(ai_clips_max, max(1, math.floor(total_scenes * 0.30)))
    ai_allocated = 0

    for idx, sc in enumerate(plan.scenes, 1):
        narr = sc.narration
        has_stats = bool(re.search(r"\b\d+(?:[.,]\d+)*(?:\s*(?:%|tỷ|triệu|nghìn|ngàn|usd|vnd|nm|hz|nit|tb|gb))\b", narr, re.I))
        suggested = suggest_metaphor_recipe(narr, idx)

        # Decide mode
        mode = "motion"
        ai_brief = None
        if not has_stats and ai_allocated < max_allowed and (idx == 1 or idx == total_scenes // 2 + 1):
            # Cảnh hook hoặc cảnh giữa không có số liệu -> dùng hybrid/ai_clip
            mode = "hybrid" if idx > 1 else "ai_clip"
            ai_allocated += 1
            ai_brief = AiClipBrief(
                prompt_en=f"cinematic shot representing modern technology concept, subtle lighting, shallow depth of field",
                fallback_recipe=suggested,
                duration_sec=4,
                camera="slow push-in"
            )

        words = narr.split()
        beats = [
            KeyBeatBrief(at_phrase=" ".join(words[:min(3, len(words))]), event="Mở đầu hình ảnh"),
            KeyBeatBrief(at_phrase=" ".join(words[len(words)//2:len(words)//2 + 3]) if len(words) > 3 else "hành động", event="Chuyển động chính"),
            KeyBeatBrief(at_phrase=" ".join(words[-min(3, len(words)):]) if len(words) > 3 else "kết thúc", event="Chốt điểm nhấn"),
        ]

        item = ScenePlanItem(
            scene_id=idx,
            mode=mode,
            rationale="Tối ưu theo chủ đề nội dung và độ sinh động trực quan",
            motion_brief=MotionBrief(
                visual_idea=f"Minh họa {sc.role}",
                recipe_candidates=[suggested, "text_focus"],
                metaphor_link="Ẩn dụ công nghệ hiện đại",
                key_beats=beats,
            ),
            emphasis=[
                EmphasisItem(
                    at_phrase=" ".join(words[:2]),
                    text=" ".join(words[:2]),
                    kind="new_term",
                    effect="bold_pop",
                    intensity="normal",
                    place="caption"
                )
            ],
            ai_clip=ai_brief
        )
        scenes.append(item)

    return ScenePlanResponse(
        style_prefix_en="cinematic, deep navy and cyan neon accents, soft volumetric light, shallow depth of field",
        ai_label_required=True,
        scenes=scenes,
        review_notes=["[scene_director, nhóm 3] Sinh kế hoạch cảnh heuristic (fallback khi không dùng LLM)."]
    )


def run_scene_director(
    project_dir: Path | str,
    plan: EditPlan,
    settings: Optional[Settings] = None,
    brief: Optional[ResearchBrief] = None,
    diagnostics: Optional[Diagnostics] = None,
) -> ScenePlanResponse:
    """Execute Scene Director stage, validate output, and write scene_plan.json."""
    project_dir = Path(project_dir)
    settings = settings or get_settings()
    ai_clips_max = getattr(settings, "ai_clips_max_per_video", 2)

    prompt = build_scene_director_prompt(plan, ai_clips_max=ai_clips_max, settings=settings)

    scene_plan: Optional[ScenePlanResponse] = None

    # Try calling LLM via Router if provider configured
    try:
        from providers.llm.router import Router, route_ready
        if route_ready(settings, "director"):
            router = Router(settings, "director", diagnostics=diagnostics)
            response_text = router.call([{"role": "user", "content": prompt}], mode="json")
            data = json.loads(response_text)
            scene_plan = ScenePlanResponse.model_validate(data)
    except Exception as exc:
        if diagnostics:
            diagnostics.record_exception(exc, "Lỗi gọi LLM Scene Director; chuyển sang heuristic.")

    if not scene_plan:
        scene_plan = generate_heuristic_scene_plan(plan, ai_clips_max=ai_clips_max)

    # Validate & Repair guardrails
    validate_and_repair_scene_plan(scene_plan, plan, ai_clips_max=ai_clips_max, brief=brief)

    # Atomic write scene_plan.json
    out_file = project_dir / "scene_plan.json"
    write_json_atomic(out_file, scene_plan.model_dump(mode="json"))

    # Append review notes to plan
    plan.review_notes.extend(n for n in scene_plan.review_notes if n not in plan.review_notes)

    return scene_plan
