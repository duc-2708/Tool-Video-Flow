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
    force_plan: bool = True,
    scale: float = 1.0,
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
        
        # Build sentences by splitting scene narrations into complete grammatical units
        import re
        sentences: list[dict[str, Any]] = []
        cur_t = 0.0
        for sc in timeline.scenes:
            w_file = p_dir / "audio" / f"scene_{sc.spec.id}.words.json"
            sc_words = read_words(w_file) if w_file.is_file() else []
            narr = sc.spec.narration.strip()
            raw_sents = [s.strip() for s in re.split(r"(?<=[.?!])\s+", narr) if s.strip()]
            if not raw_sents:
                raw_sents = [narr]
            tot_words = sum(max(1, len(s.split())) for s in raw_sents)
            sc_t = cur_t
            for s_text in raw_sents:
                w_cnt = max(1, len(s_text.split()))
                s_dur = sc.duration * (w_cnt / max(1, tot_words))
                sentences.append({
                    "id": len(sentences) + 1,
                    "scene_id": sc.spec.id,
                    "text": s_text,
                    "start": round(sc_t, 3),
                    "end": round(sc_t + s_dur, 3),
                    "duration": round(s_dur, 3),
                    "words": sc_words,
                })
                sc_t += s_dur
            cur_t += sc.duration

        # Capture sources
        source_captures = capture_sources_for_brief(brief_data, p_dir)

        # Plan slides
        # If confirm_cost is False, we use deterministic heuristic planner (0 remote API cost)
        if not confirm_cost:
            if not force_plan and (p_dir / "slide_script.json").is_file():
                try:
                    slide_script_obj = SlideScript.model_validate_json((p_dir / "slide_script.json").read_text(encoding="utf-8"))
                    logger.info("Loaded existing slide_script.json (%d slides)", len(slide_script_obj.slides))
                except Exception:
                    slide_script_obj = None
            if not slide_script_obj:
                # Safe offline mode: no remote LLM cost
                logger.info("Generating deterministic heuristic planner (0 remote API cost)")
                from editor.motion.light_glass_slots import create_heuristic_slide_script
                slide_script_obj = create_heuristic_slide_script(
                    sentences=sentences,
                    brief=brief_data,
                    total_duration=total_duration,
                    brand_name=getattr(settings, "brand_name", ""),
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
                brand_name=getattr(settings, "brand_name", ""),
            )

        # Synthesize & resolve imagery with fail-closed CV filters (face detection + text/slide rejection)
        from pipeline.slide_image_resolver import resolve_images_for_slide_script
        resolved_imgs = resolve_images_for_slide_script(p_dir, slide_script_obj, force_refresh=force_plan)
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
    parser.add_argument("--force-plan", action=argparse.BooleanOptionalAction, default=False, help="Force regenerate SlideScript")
    parser.add_argument("--scale", type=float, default=1.0, choices=[0.25, 0.5, 1.0], help="Render scale")
    parser.add_argument("--fps", type=int, default=30, choices=[24, 30], help="Render FPS")
    parser.add_argument("--no-audit", action="store_true", help="Disable post-render audit")

    args = parser.parse_args()
    res = rerender_project_with_theme(
        project_dir=args.project,
        theme=args.theme,
        use_slide_script=args.slide_script,
        confirm_cost=args.confirm_cost,
        force_plan=args.force_plan,
        scale=args.scale,
        fps=args.fps,
        run_audit=not args.no_audit,
    )
    print(json.dumps(res.get("audit", {}), indent=2, ensure_ascii=False))
