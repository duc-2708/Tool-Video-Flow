"""Re-render existing projects with themes (such as light_glass) and SlideScript flow.

Supports:
- Loading existing project (brief, audio, edit_plan)
- --slide-script: runs slide_planner -> slide_grounding -> captures source citations -> renders slide MP4
- --confirm-cost: only calls real LLM if explicitly confirmed; otherwise uses mock/heuristic planner
- Running automated audit_style.py and printing structured report
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.slide_planner import plan_slides
from config.settings import get_settings
from editor.motion.slide_grounding import verify_and_ground_slides
from editor.render import run_render
from editor.timeline import build_timeline
from schemas.slide_script import SlideScript
from tools.audit_style import audit_light_glass_project
from tools.source_capture import capture_sources_for_brief
from utils.atomic_io import read_json_atomic, write_json_atomic
from utils.diagnostics import Diagnostics
from utils.word_timing import read_words

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def rerender_project_with_theme(
    project_dir: Path | str,
    theme: str = "light_glass",
    use_slide_script: bool = True,
    confirm_cost: bool = False,
    scale: float = 0.5,
    fps: int = 30,
    run_audit: bool = True,
) -> dict[str, Any]:
    """Re-render an existing project directory with specified theme and optional slide script."""
    p_dir = Path(project_dir).resolve()
    if not p_dir.is_dir():
        raise FileNotFoundError(f"Project directory not found: {p_dir}")

    settings = get_settings().model_copy(update={
        "motion_enabled": True,
        "motion_theme": theme,
        "motion_scale": scale,
        "motion_fps": fps,
    })
    diagnostics = Diagnostics(settings.logs_dir, filename="rerender_theme.log")

    plan_file = p_dir / "edit_plan.resolved.json"
    if not plan_file.is_file():
        plan_file = p_dir / "edit_plan.json"
    brief_file = p_dir / "brief.json"

    if not plan_file.is_file():
        raise FileNotFoundError(f"edit_plan.json or edit_plan.resolved.json missing in project: {p_dir}")

    brief_data = read_json_atomic(brief_file) if brief_file.is_file() else {}
    plan_data = read_json_atomic(plan_file)

    timeline = build_timeline(plan_file)
    total_duration = sum(sc.duration for sc in timeline.scenes)

    # 1. Slide Script planning if requested
    slide_script_obj: SlideScript | None = None
    if use_slide_script and theme == "light_glass":
        logger.info("Building Slide Script for project %s (total duration: %.2fs)", p_dir.name, total_duration)
        
        # Build sentences
        sentences: list[dict[str, Any]] = []
        cur_t = 0.0
        for sc in timeline.scenes:
            w_file = p_dir / "audio" / f"scene_{sc.spec.id}.words.json"
            sc_words = read_words(w_file) if w_file.is_file() else []
            sentences.append({
                "id": sc.spec.id,
                "text": sc.spec.narration,
                "start": cur_t,
                "end": cur_t + sc.duration,
                "words": sc_words,
            })
            cur_t += sc.duration

        # Capture sources
        source_captures = capture_sources_for_brief(brief_data, p_dir)
        first_img_path = None
        if source_captures:
            first_meta = next(iter(source_captures.values()))
            first_img_path = first_meta.get("image_path")

        # Plan slides
        # If confirm_cost is False, we pass a mock LLM or let plan_slides use heuristic
        mock_client = None
        if not confirm_cost:
            if (p_dir / "slide_script.json").is_file():
                try:
                    slide_script_obj = SlideScript.model_validate_json((p_dir / "slide_script.json").read_text(encoding="utf-8"))
                    logger.info("Loaded existing slide_script.json (%d slides)", len(slide_script_obj.slides))
                except Exception:
                    slide_script_obj = None
            if not slide_script_obj:
                # Safe offline mode: no remote LLM cost
                logger.info("confirm_cost is False: using deterministic heuristic planner (0 remote API cost)")
                from editor.motion.light_glass_slots import create_heuristic_slide_script
                slide_script_obj = create_heuristic_slide_script(
                    sentences=sentences,
                    brief=brief_data,
                    total_duration=total_duration,
                    brand_name=getattr(settings, "brand_name", "TIN CÔNG NGHỆ"),
                )
                slide_script_obj = verify_and_ground_slides(slide_script_obj, {s["id"]: s for s in sentences}, brief_data)
        else:
            # Token and cost estimation before calling remote LLM
            est_in = max(100, len(sentences) * 120 + 400)
            est_out = max(100, round(total_duration / 6.5) * 120)
            est_cost = (est_in * 0.15 + est_out * 0.60) / 1_000_000
            print(f"[COST ESTIMATE] Slide Planner token estimate: ~{est_in} in, ~{est_out} out (~${est_cost:.5f}). Calling confirmed LLM...")
            logger.info("confirm_cost=True: calling Slide Planner LLM (~%d in, ~%d out, ~$%.5f)", est_in, est_out, est_cost)
            slide_script_obj = plan_slides(
                brief=brief_data,
                sentences=sentences,
                total_duration=total_duration,
                settings=settings,
                diagnostics=diagnostics,
                brand_name=getattr(settings, "brand_name", "TIN CÔNG NGHỆ"),
            )

        # Attach captured images across slides
        if source_captures and slide_script_obj.slides:
            captures_list = [c.get("image_path") for c in source_captures.values() if c.get("image_path")]
            if captures_list:
                # Slide 1 gets primary capture if not already set
                if not slide_script_obj.slides[0].slots.get("image_url"):
                    slide_script_obj.slides[0].slots["image_url"] = str(captures_list[0])
                # Distribute remaining captures to other slides (e.g. slide 3, 4)
                if len(captures_list) > 1 and len(slide_script_obj.slides) > 3:
                    target_slide = slide_script_obj.slides[3]
                    if not target_slide.slots.get("image_url") and target_slide.layout in ("lg_source_headline", "lg_shot_features", "lg_stat_hero", "lg_note_card"):
                        target_slide.slots["image_url"] = str(captures_list[1])
                if len(captures_list) > 2 and len(slide_script_obj.slides) > 4:
                    target_slide = slide_script_obj.slides[4]
                    if not target_slide.slots.get("image_url") and target_slide.layout in ("lg_source_headline", "lg_shot_features", "lg_stat_hero"):
                        target_slide.slots["image_url"] = str(captures_list[2])

        # Synthesize & resolve high-contrast cinematic imagery for all slides
        from pipeline.slide_image_resolver import resolve_images_for_slide_script
        resolved_imgs = resolve_images_for_slide_script(p_dir, slide_script_obj, force_refresh=True)
        logger.info("Resolved %d visual graphic assets for slides", len(resolved_imgs))

        # Save slide_script.json
        slide_script_file = p_dir / "slide_script.json"
        write_json_atomic(slide_script_file, slide_script_obj.model_dump(mode="json"))
        logger.info("Saved slide_script.json with %d slides", len(slide_script_obj.slides))

    # 2. Render video
    render_out = p_dir / "render"
    render_out.mkdir(parents=True, exist_ok=True)
    video_dest = render_out / f"{p_dir.name}_{theme}.mp4"

    logger.info("Starting render (scale=%.2f, fps=%d)", scale, fps)
    render_result = run_render(
        plan_path=plan_file,
        mode="final",
        settings=settings,
        diagnostics=diagnostics,
    )
    video_dest = Path(render_result.get("path") or (render_out / f"{p_dir.name}_{theme}.mp4"))

    audit_result = {}
    if run_audit and video_dest.is_file():
        logger.info("Running automated audit_style on %s", video_dest.name)
        audit_result = audit_light_glass_project(
            project_dir=p_dir,
            video_path=video_dest,
            slide_script=slide_script_obj,
        )

    return {
        "project": str(p_dir),
        "video_path": str(video_dest),
        "render_result": render_result,
        "slide_script": slide_script_obj.model_dump(mode="json") if slide_script_obj else None,
        "audit": audit_result,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-render project with theme and SlideScript flow")
    parser.add_argument("--project", required=True, help="Path to project directory")
    parser.add_argument("--theme", default="light_glass", help="Motion theme (default: light_glass)")
    parser.add_argument("--slide-script", action="store_true", default=True, help="Enable SlideScript flow")
    parser.add_argument("--confirm-cost", action="store_true", default=False, help="Explicit confirmation for remote LLM API calls")
    parser.add_argument("--scale", type=float, default=0.5, choices=[0.25, 0.5, 1.0], help="Render scale")
    parser.add_argument("--fps", type=int, default=30, choices=[24, 30], help="Render FPS")
    parser.add_argument("--no-audit", action="store_true", help="Disable post-render audit")

    args = parser.parse_args()
    res = rerender_project_with_theme(
        project_dir=args.project,
        theme=args.theme,
        use_slide_script=args.slide_script,
        confirm_cost=args.confirm_cost,
        scale=args.scale,
        fps=args.fps,
        run_audit=not args.no_audit,
    )
    print(json.dumps(res.get("audit", {}), indent=2, ensure_ascii=False))
