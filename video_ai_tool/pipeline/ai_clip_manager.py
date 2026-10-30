"""AI Clip Manager (Phase 8): Orchestrates AI video clip generation, manual imports, and caching.
Provides strict governance for AI video clips via Hinton gateway, manual files, or deterministic fallback.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any, Optional

from config.settings import Settings, get_settings
from schemas.scene_director import ScenePlanResponse, ScenePlanItem
from utils.atomic_io import read_json_atomic, write_json_atomic, copy_file_atomic
from utils.diagnostics import Diagnostics
from utils.media import video_info
from providers.video_gateway import VideoRequest, MODELS


def get_manual_clip_path(project_dir: Path, scene_id: int) -> Optional[Path]:
    """Find user-provided video in ai_clips_manual/ for a given scene."""
    manual_dir = project_dir / "ai_clips_manual"
    if not manual_dir.is_dir():
        return None

    # Priority 1: Match scene_{scene_id}.* or scene{scene_id}.*
    candidates = [
        manual_dir / f"scene_{scene_id}.mp4",
        manual_dir / f"scene_{scene_id}.mov",
        manual_dir / f"scene_{scene_id}_clip.mp4",
        manual_dir / f"scene{scene_id}.mp4",
        manual_dir / f"scene_{scene_id}.webm",
    ]
    for c in candidates:
        if c.is_file() and c.stat().st_size > 1024:
            return c

    # Priority 2: Any mp4/mov in manual_dir matching scene_id in stem
    for f in manual_dir.iterdir():
        if f.is_file() and f.suffix.lower() in (".mp4", ".mov", ".webm"):
            if str(scene_id) in f.stem and f.stat().st_size > 1024:
                return f

    # Priority 3: If exactly 1 video file in manual_dir and total AI scenes == 1
    video_files = [f for f in manual_dir.iterdir() if f.is_file() and f.suffix.lower() in (".mp4", ".mov", ".webm") and f.stat().st_size > 1024]
    if len(video_files) == 1:
        return video_files[0]

    return None


def calculate_clip_cache_key(prompt_en: str, model: str, duration_sec: int, format_name: str = "tiktok") -> str:
    """Deterministic sha256 hash for AI clip caching."""
    seed = f"{prompt_en.strip()}::{model.strip()}::{duration_sec}::{format_name}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def find_cached_ai_clip(project_dir: Path, cache_key_str: str) -> Optional[Path]:
    """Search for existing finished AI clip matching cache key."""
    # Check project ai_video/ folder
    ai_video_dir = project_dir / "ai_video"
    if ai_video_dir.is_dir():
        for job_file in ai_video_dir.glob("*.json"):
            try:
                data = json.loads(job_file.read_text(encoding="utf-8"))
                if data.get("cache_key") == cache_key_str and data.get("status") == "succeeded":
                    clip_p = project_dir / data.get("clip_path", "")
                    if clip_p.is_file() and clip_p.stat().st_size > 1024:
                        return clip_p
            except Exception:
                pass

    # Check clips/ folder directly
    clips_dir = project_dir / "clips"
    if clips_dir.is_dir():
        for clip_file in clips_dir.glob(f"*{cache_key_str[:16]}*.mp4"):
            if clip_file.is_file() and clip_file.stat().st_size > 1024:
                return clip_file

    return None


def estimate_ai_clips_cost(
    scene_plan: ScenePlanResponse,
    settings: Optional[Settings] = None
) -> dict[str, Any]:
    """Estimate cost and turnaround time for AI clips in the scene plan."""
    settings = settings or get_settings()
    model = settings.ai_clip_model or settings.gateway_video_model or "veo-3.1"
    model_costs = {
        "veo-3.1": 18000,
        "seedance-2.5-30s": 12000,
    }
    unit_cost = model_costs.get(model, 18000)

    ai_scenes = [s for s in scene_plan.scenes if s.mode in ("ai_clip", "hybrid")]
    max_allowed = getattr(settings, "ai_clips_max_per_video", 2)
    scenes_to_render = ai_scenes[:max_allowed]
    count = len(scenes_to_render)

    total_cost = count * unit_cost
    wait_sec = count * 60  # average 60s per clip

    return {
        "count": count,
        "scenes_eligible": [s.scene_id for s in scenes_to_render],
        "model": model,
        "unit_cost_vnd": unit_cost,
        "total_cost_vnd": total_cost,
        "estimated_wait_sec": wait_sec,
        "auto_approve": getattr(settings, "ai_clip_auto_approve", False),
        "mode": getattr(settings, "ai_clip_mode", "off"),
    }


def resolve_scene_ai_clip(
    project_dir: Path | str,
    scene_item: ScenePlanItem,
    settings: Optional[Settings] = None,
    diagnostics: Optional[Diagnostics] = None,
    approved_prompts: Optional[dict[int, dict]] = None,
) -> dict[str, Any]:
    """Resolve an AI clip for a given scene item:
    - Mode 'off' -> fallback to motion
    - Mode 'manual' -> look up in ai_clips_manual/
    - Mode 'auto' -> check cache or invoke Hinton gateway
    Always records source and 'AI' label in metadata.
    """
    project_dir = Path(project_dir)
    settings = settings or get_settings()

    fallback_recipe = (
        scene_item.ai_clip.fallback_recipe
        if scene_item.ai_clip and scene_item.ai_clip.fallback_recipe
        else (scene_item.motion_brief.recipe_candidates[0] if scene_item.motion_brief.recipe_candidates else "text_focus")
    )

    if scene_item.mode not in ("ai_clip", "hybrid"):
        return {
            "resolved": False,
            "mode": "motion",
            "fallback_to_motion": False,
            "recipe": fallback_recipe
        }

    clip_mode = getattr(settings, "ai_clip_mode", "off").lower()

    # 1. Mode OFF -> immediate fallback to motion
    if clip_mode == "off":
        return {
            "resolved": False,
            "mode": scene_item.mode,
            "fallback_to_motion": True,
            "reason": "AI_CLIP_MODE=off: chế độ clip AI đang tắt; tự động chuyển sang hoạt họa motion.",
            "recipe": fallback_recipe,
            "source": "motion_fallback",
            "label": "AI_skipped"
        }

    # 2. Mode MANUAL -> inspect ai_clips_manual/
    if clip_mode == "manual":
        manual_p = get_manual_clip_path(project_dir, scene_item.scene_id)
        if manual_p and manual_p.is_file():
            clips_dir = project_dir / "clips"
            clips_dir.mkdir(parents=True, exist_ok=True)
            dest_clip = clips_dir / f"scene_{scene_item.scene_id}_ai_manual.mp4"
            copy_file_atomic(manual_p, dest_clip)

            meta = {
                "resolved": True,
                "mode": scene_item.mode,
                "fallback_to_motion": False,
                "source": "AI_manual",
                "ai_generated": True,
                "label": "AI",
                "clip_path": str(dest_clip.relative_to(project_dir)).replace("\\", "/"),
                "original_filename": manual_p.name,
                "recipe": fallback_recipe
            }
            try:
                vinfo = video_info(dest_clip)
                meta.update({
                    "width": vinfo.get("width"),
                    "height": vinfo.get("height"),
                    "duration_sec": vinfo.get("duration"),
                })
            except Exception:
                pass
            return meta
        else:
            return {
                "resolved": False,
                "mode": scene_item.mode,
                "fallback_to_motion": True,
                "reason": f"Không tìm thấy clip nhập tay trong ai_clips_manual/ cho cảnh {scene_item.scene_id}; fallback motion.",
                "recipe": fallback_recipe,
                "source": "motion_fallback",
                "label": "AI_missing_manual"
            }

    # 3. Mode AUTO -> Cache lookup or Hinton Gateway
    prompt_en = scene_item.ai_clip.prompt_en if scene_item.ai_clip else ""
    if approved_prompts and scene_item.scene_id in approved_prompts:
        prompt_en = approved_prompts[scene_item.scene_id].get("prompt_en", prompt_en)

    model = settings.ai_clip_model or settings.gateway_video_model or "veo-3.1"
    dur_sec = scene_item.ai_clip.duration_sec if scene_item.ai_clip else 4

    cache_k = calculate_clip_cache_key(prompt_en, model, dur_sec)
    cached_file = find_cached_ai_clip(project_dir, cache_k)

    if cached_file and cached_file.is_file():
        meta = {
            "resolved": True,
            "mode": scene_item.mode,
            "fallback_to_motion": False,
            "source": "AI_cache",
            "ai_generated": True,
            "label": "AI",
            "clip_path": str(cached_file.relative_to(project_dir)).replace("\\", "/"),
            "cache_key": cache_k,
            "recipe": fallback_recipe
        }
        return meta

    # Approval check if not auto-approve
    auto_approve = getattr(settings, "ai_clip_auto_approve", False)
    is_approved = auto_approve or (approved_prompts and approved_prompts.get(scene_item.scene_id, {}).get("approved", False))

    if not is_approved:
        return {
            "resolved": False,
            "mode": scene_item.mode,
            "fallback_to_motion": True,
            "reason": f"Cảnh {scene_item.scene_id} chưa được người dùng duyệt prompt; tự động dùng motion fallback.",
            "recipe": fallback_recipe,
            "source": "motion_fallback",
            "label": "AI_not_approved"
        }

    # Gateway API key presence check
    gateway_key = settings.gateway_api_key.get_secret_value().strip()
    if not gateway_key:
        return {
            "resolved": False,
            "mode": scene_item.mode,
            "fallback_to_motion": True,
            "reason": "GATEWAY_API_KEY chưa được cấu hình; tự động chuyển sang hoạt họa motion.",
            "recipe": fallback_recipe,
            "source": "motion_fallback",
            "label": "AI_no_key"
        }

    # Execute paid creation via existing durable pipeline/ai_video.py
    try:
        from pipeline.ai_video import create_job, resume_job
        request = VideoRequest(
            model=model,
            prompt=prompt_en,
            seconds=dur_sec,
            format="tiktok"
        )
        job_path = create_job(project_dir, request, settings)
        stall_sec = getattr(settings, "ai_clip_stall_sec", 120)
        final_job = resume_job(job_path, settings, wait_sec=stall_sec)

        if final_job.get("status") == "succeeded" and final_job.get("clip_path"):
            clip_res = project_dir / final_job["clip_path"]
            if clip_res.is_file():
                return {
                    "resolved": True,
                    "mode": scene_item.mode,
                    "fallback_to_motion": False,
                    "source": "AI",
                    "ai_generated": True,
                    "label": "AI",
                    "clip_path": final_job["clip_path"],
                    "cache_key": cache_k,
                    "recipe": fallback_recipe
                }

        # Failed or timeout
        err_msg = final_job.get("error") or "Không tải được clip từ gateway"
        return {
            "resolved": False,
            "mode": scene_item.mode,
            "fallback_to_motion": True,
            "reason": f"Tạo clip AI thất bại ({err_msg}); tự động fallback về hoạt họa motion.",
            "recipe": fallback_recipe,
            "source": "motion_fallback",
            "label": "AI_failed"
        }
    except Exception as exc:
        if diagnostics:
            diagnostics.record_exception(exc, f"Lỗi tạo clip AI cảnh {scene_item.scene_id}")
        return {
            "resolved": False,
            "mode": scene_item.mode,
            "fallback_to_motion": True,
            "reason": f"Ngoại lệ khi gọi cổng AI ({exc}); fallback về hoạt họa motion.",
            "recipe": fallback_recipe,
            "source": "motion_fallback",
            "label": "AI_exception"
        }


def save_prompt_approvals(project_dir: Path | str, approvals: dict[int, dict]) -> None:
    """Save user approvals of AI clip prompts to ai_prompt_approvals.json."""
    project_dir = Path(project_dir)
    out_file = project_dir / "ai_prompt_approvals.json"
    write_json_atomic(out_file, approvals)


def load_prompt_approvals(project_dir: Path | str) -> dict[int, dict]:
    """Load user approvals of AI clip prompts."""
    project_dir = Path(project_dir)
    f = project_dir / "ai_prompt_approvals.json"
    if f.is_file():
        try:
            raw = read_json_atomic(f)
            return {int(k): v for k, v in raw.items()}
        except Exception:
            pass
    return {}
