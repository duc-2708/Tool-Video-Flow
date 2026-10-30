"""Hybrid Rendering & Composition Engine (Phase 8).
Coordinates seamless blending of AI video clips and programmable motion graphics:
- 'motion': Pure SVG/CSS deterministic animations.
- 'ai_clip': AI clip as primary visual, speed adjusted, vignette, theme toned, simple labels.
- 'hybrid': AI clip as darkened, softly blurred background + rich motion overlay.
Ensures subtitle zone contrast >= 4.5:1 (WCAG AA), deterministic fallback on error,
and "hình mô phỏng" compliance disclosure.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageStat

from config.settings import Settings, get_settings
from pipeline.ai_clip_manager import resolve_scene_ai_clip
from schemas.scene_director import ScenePlanResponse, ScenePlanItem
from utils.atomic_io import read_json_atomic


def calculate_luma(image: Image.Image) -> float:
    """Calculate ITU-R BT.601 perceptual luminance of an image."""
    rgb = image.convert("RGB")
    stat = ImageStat.Stat(rgb)
    r, g, b = stat.mean[:3]
    return 0.299 * r + 0.587 * g + 0.114 * b


def check_subtitle_contrast(image: Image.Image, y_start: int = 1380, y_end: int = 1700) -> float:
    """Measure background luminance in the protected subtitle area (1380-1700 px).
    Returns mean luma (0-255). A value < 80 ensures contrast >= 4.5:1 with light text.
    """
    w, h = image.size
    ys = int(y_start * h / 1920)
    ye = int(y_end * h / 1920)
    zone = image.crop((0, ys, w, ye))
    return calculate_luma(zone)


def apply_caption_gradient(
    image: Image.Image,
    y_start: int = 1180,
    y_end: int = 1750,
    max_alpha: int = 240,
) -> Image.Image:
    """Apply a smooth dark vertical gradient over the bottom zone to protect subtitle legibility."""
    w, h = image.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    ys = int(y_start * h / 1920)
    ye = int(y_end * h / 1920)
    y_ramp = int(ys + (ye - ys) * 0.35)

    for y in range(ys, h):
        if y < y_ramp:
            progress = (y - ys) / max(1, y_ramp - ys)
            alpha = int((progress ** 1.2) * max_alpha)
        else:
            alpha = max_alpha
        draw.line([(0, y), (w, y)], fill=(6, 10, 20, alpha))

    base = image.convert("RGBA")
    combined = Image.alpha_composite(base, overlay)
    return combined.convert("RGB")


def apply_vignette(image: Image.Image, strength: float = 0.45) -> Image.Image:
    """Apply a smooth radial vignette darkening towards corners."""
    w, h = image.size
    Y, X = np.ogrid[:h, :w]
    cx, cy = w / 2.0, h / 2.0
    dist = np.sqrt(((X - cx) / cx) ** 2 + ((Y - cy) / cy) ** 2)
    vignette = np.clip(1.0 - (dist - 0.4) * strength, 0.0, 1.0)
    arr = np.array(image.convert("RGB"), dtype=np.float32)
    arr = arr * vignette[..., None]
    return Image.fromarray(np.clip(arr, 0.0, 255.0).astype(np.uint8))


def process_clip_to_frames(
    clip_path: Path,
    scene_duration: float,
    mode: str = "hybrid",
    fps: int = 8,
    target_width: int = 360,
    target_height: int = 640,
) -> list[str]:
    """Extract, tone, filter, and encode clip frames into base64 JPEG data URLs:
    - Speed adjustment: <= ±15% if close to scene duration.
    - Loop / hold: smooth loop when shorter than scene duration.
    - 'hybrid': 35-50% brightness (0.55), soft blur (5px), vignette, caption gradient.
    - 'ai_clip': crisp (0 blur), 0.90 brightness, vignette, caption gradient.
    """
    from editor.runtime import VideoFileClip

    frames: list[str] = []
    with VideoFileClip(str(clip_path), audio=False) as video:
        clip_dur = max(0.5, float(video.duration))
        ratio = scene_duration / clip_dur

        # Speed adjustment if within ±15%
        if 0.85 <= ratio <= 1.15:
            effective_speed = clip_dur / scene_duration
        else:
            effective_speed = 1.0

        total_frames = max(1, int(math.ceil(scene_duration * fps)))

        for i in range(total_frames):
            t_scene = min(scene_duration - 1e-4, i / fps)
            if 0.85 <= ratio <= 1.15:
                t_clip = min(clip_dur - 1e-4, t_scene * effective_speed)
            elif clip_dur < scene_duration:
                t_clip = t_scene % clip_dur
            else:
                t_clip = min(clip_dur - 1e-4, t_scene)

            frame_arr = video.get_frame(t_clip)
            frame_img = Image.fromarray(frame_arr)

            # Fit canvas
            frame_img.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
            if frame_img.size != (target_width, target_height):
                bg = Image.new("RGB", (target_width, target_height), (10, 16, 28))
                offset_x = (target_width - frame_img.width) // 2
                offset_y = (target_height - frame_img.height) // 2
                bg.paste(frame_img, (offset_x, offset_y))
                frame_img = bg

            if mode == "hybrid":
                # Darken 35-50% (brightness 0.55 = -45%)
                frame_img = ImageEnhance.Brightness(frame_img).enhance(0.55)
                # Soft blur
                frame_img = frame_img.filter(ImageFilter.GaussianBlur(5))
                # Radial vignette
                frame_img = apply_vignette(frame_img, strength=0.45)
                # Subtitle gradient protection
                frame_img = apply_caption_gradient(frame_img, max_alpha=200)
                # Verify subtitle contrast
                luma = check_subtitle_contrast(frame_img)
                if luma > 75:
                    frame_img = apply_caption_gradient(frame_img, max_alpha=230)
            elif mode == "ai_clip":
                # Crisp visual focus (no blur)
                frame_img = ImageEnhance.Brightness(frame_img).enhance(0.90)
                # Mild vignette
                frame_img = apply_vignette(frame_img, strength=0.30)
                # Subtitle gradient protection
                frame_img = apply_caption_gradient(frame_img, max_alpha=180)

            # Encode to JPEG base64
            buf = io.BytesIO()
            frame_img.save(buf, format="JPEG", quality=65)
            b64_str = base64.b64encode(buf.getvalue()).decode("ascii")
            frames.append(f"data:image/jpeg;base64,{b64_str}")

    return frames


def prepare_scene_hybrid_payload(
    scene_id: int,
    scene_duration: float,
    project_dir: Path | str,
    settings: Optional[Settings] = None,
    diagnostics: Optional[Any] = None,
    approved_prompts: Optional[dict[int, dict]] = None,
) -> dict[str, Any]:
    """Determine mode and build AI background payload for a scene:
    Returns dict:
      - 'mode': 'motion' | 'hybrid' | 'ai_clip'
      - 'ai_backgrounds': list of background descriptor dicts
      - 'fallback_to_motion': bool
      - 'fallback_recipe': Optional[str]
      - 'reason': Optional[str]
      - 'badge_label': "hình mô phỏng" if AI clip used
    """
    settings = settings or get_settings()
    project_dir = Path(project_dir)

    # 1. Global toggle check
    clip_mode = getattr(settings, "ai_clip_mode", "off").lower()
    if clip_mode == "off":
        return {
            "mode": "motion",
            "ai_backgrounds": [],
            "fallback_to_motion": False,
            "badge_label": None,
            "clip_path": None,
        }

    # 2. Check scene_plan.json
    plan_path = project_dir / "scene_plan.json"
    if not plan_path.is_file():
        return {
            "mode": "motion",
            "ai_backgrounds": [],
            "fallback_to_motion": False,
            "badge_label": None,
            "clip_path": None,
        }

    try:
        scene_plan = ScenePlanResponse.model_validate_json(plan_path.read_text(encoding="utf-8"))
    except Exception as exc:
        if diagnostics:
            diagnostics.record_exception(exc, "Không parse được scene_plan.json; dùng motion")
        return {
            "mode": "motion",
            "ai_backgrounds": [],
            "fallback_to_motion": True,
            "reason": f"Lỗi đọc scene_plan.json: {exc}",
            "badge_label": None,
            "clip_path": None,
        }

    item = next((s for s in scene_plan.scenes if s.scene_id == scene_id), None)
    if not item or item.mode == "motion":
        return {
            "mode": "motion",
            "ai_backgrounds": [],
            "fallback_to_motion": False,
            "badge_label": None,
            "clip_path": None,
        }

    # 3. Resolve AI clip
    try:
        resolved = resolve_scene_ai_clip(
            project_dir=project_dir,
            scene_item=item,
            settings=settings,
            diagnostics=diagnostics,
            approved_prompts=approved_prompts,
        )
    except Exception as exc:
        if diagnostics:
            diagnostics.record_exception(exc, f"Ngoại lệ resolve_scene_ai_clip cảnh {scene_id}")
        return {
            "mode": "motion",
            "ai_backgrounds": [],
            "fallback_to_motion": True,
            "fallback_recipe": item.ai_clip.fallback_recipe if item.ai_clip else "stat_number",
            "reason": f"Lỗi resolve clip: {exc}",
            "badge_label": None,
            "clip_path": None,
        }

    if resolved.get("fallback_to_motion") or not resolved.get("resolved"):
        return {
            "mode": "motion",
            "ai_backgrounds": [],
            "fallback_to_motion": True,
            "fallback_recipe": resolved.get("recipe") or (item.ai_clip.fallback_recipe if item.ai_clip else "stat_number"),
            "reason": resolved.get("reason", "AI clip không sẵn sàng; dùng fallback recipe"),
            "badge_label": None,
            "clip_path": None,
        }

    clip_rel_p = resolved.get("clip_path")
    if not clip_rel_p:
        return {
            "mode": "motion",
            "ai_backgrounds": [],
            "fallback_to_motion": True,
            "fallback_recipe": resolved.get("recipe", "stat_number"),
            "reason": "Thiếu clip_path sau khi resolve",
            "badge_label": None,
            "clip_path": None,
        }

    clip_full_p = project_dir / clip_rel_p
    if not clip_full_p.is_file() or clip_full_p.stat().st_size < 1024:
        return {
            "mode": "motion",
            "ai_backgrounds": [],
            "fallback_to_motion": True,
            "fallback_recipe": resolved.get("recipe", "stat_number"),
            "reason": f"File clip không tồn tại hoặc rỗng ({clip_rel_p})",
            "badge_label": None,
            "clip_path": None,
        }

    # 4. Extract and tone frames
    try:
        fps = 8
        frames = process_clip_to_frames(
            clip_path=clip_full_p,
            scene_duration=scene_duration,
            mode=item.mode,
            fps=fps,
        )
        return {
            "mode": item.mode,
            "ai_backgrounds": [{
                "start": 0.0,
                "duration": scene_duration,
                "frames": frames,
                "fps": fps,
                "mode": item.mode,
                "clip_path": clip_rel_p,
                "badge": "hình mô phỏng",
            }],
            "fallback_to_motion": False,
            "badge_label": "hình mô phỏng",
            "clip_path": clip_rel_p,
            "source": resolved.get("source", "AI"),
        }
    except Exception as exc:
        if diagnostics:
            diagnostics.record_exception(exc, f"Lỗi decode clip frames cảnh {scene_id}")
        return {
            "mode": "motion",
            "ai_backgrounds": [],
            "fallback_to_motion": True,
            "fallback_recipe": resolved.get("recipe", "stat_number"),
            "reason": f"Lỗi xử lý frame clip AI: {exc}",
            "badge_label": None,
            "clip_path": None,
        }
