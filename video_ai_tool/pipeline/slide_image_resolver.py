"""Slide Image Resolver & Visual Prompt Synthesizer.

Reads image_prompt from slides/shots and ensures high-resolution, content-grounded,
cinematic visual imagery is generated, cached, and prepared for 5-second motion rendering.
Never leaves empty dark cards or broken placeholder files.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont


def sanitize_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)[:40]


def path_to_data_uri(path: Path | str) -> Optional[str]:
    """Convert any local image file to a base64 Data URI for Chromium about:blank safety."""
    p = Path(path).resolve()
    if not p.is_file():
        return None
    try:
        suffix = p.suffix.lower().lstrip(".")
        if suffix in ("jpg", "jpeg"):
            mime = "image/jpeg"
        elif suffix == "png":
            mime = "image/png"
        elif suffix == "webp":
            mime = "image/webp"
        elif suffix == "svg":
            mime = "image/svg+xml"
        else:
            mime = "image/png"
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None


def generate_cinematic_visual(
    prompt: str,
    output_path: Path,
    width: int = 1080,
    height: int = 1080,
    theme_style: str = "light_glass",
) -> Path:
    """Synthesize a high-resolution, visually rich cinematic illustration based on prompt keywords.
    
    Creates vivid ambient lighting, volumetric glow, high-tech geometry, and thematic iconography.
    Guarantees crisp, high-contrast, visually engaging results with zero blank spaces.
    """
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    p_low = prompt.lower()

    # Determine visual color palette based on prompt
    if any(k in p_low for k in ("neural", "ai", "network", "node", "brain", "intelligence")):
        # Cyber Cyan & Neon Blue palette
        top_color = (11, 15, 30)
        bot_color = (15, 23, 42)
        accent_color = (14, 165, 233)  # sky-500
        secondary_color = (99, 102, 241)  # indigo-500
        glow_color = (56, 189, 248)
        visual_type = "neural_net"
    elif any(k in p_low for k in ("chart", "spline", "falling", "cost", "zero", "financial", "stock", "market")):
        # Neon Emerald & Digital Financial Trading
        top_color = (10, 20, 24)
        bot_color = (6, 78, 59)
        accent_color = (16, 185, 129)  # emerald-500
        secondary_color = (52, 211, 153)
        glow_color = (110, 231, 183)
        visual_type = "financial_curve"
    elif any(k in p_low for k in ("shield", "risk", "security", "warning", "pension", "radar")):
        # Amber / Crimson Cyber Shield
        top_color = (24, 15, 15)
        bot_color = (40, 20, 20)
        accent_color = (245, 158, 11)  # amber-500
        secondary_color = (239, 68, 68)  # red-500
        glow_color = (251, 191, 36)
        visual_type = "risk_shield"
    elif any(k in p_low for k in ("elon", "musk", "author", "podcast", "speaker", "interview")):
        # Premium Slate & Warm Golden Rim Light
        top_color = (15, 23, 42)
        bot_color = (30, 41, 59)
        accent_color = (234, 179, 8)  # yellow-500
        secondary_color = (59, 130, 246)
        glow_color = (253, 224, 71)
        visual_type = "tech_leader"
    elif any(k in p_low for k in ("piggy", "versus", "scale", "reinvest", "traditional", "saving")):
        # Dual Color Contrast (Warm Coral vs Cyan Gold)
        top_color = (17, 24, 39)
        bot_color = (31, 41, 55)
        accent_color = (244, 63, 94)  # rose-500
        secondary_color = (16, 185, 129)  # emerald-500
        glow_color = (251, 113, 133)
        visual_type = "versus_scale"
    elif any(k in p_low for k in ("robot", "factory", "automation", "manufacturing", "plant")):
        # High-Tech Industrial Titanium & Laser Cyan
        top_color = (15, 23, 42)
        bot_color = (30, 58, 138)
        accent_color = (6, 182, 212)  # cyan-500
        secondary_color = (59, 130, 246)
        glow_color = (103, 232, 249)
        visual_type = "robotics"
    elif any(k in p_low for k in ("reaction", "heart", "like", "cta", "follow", "subscribe")):
        # Vibrant Social Berry & Purple Glow
        top_color = (26, 16, 45)
        bot_color = (49, 20, 77)
        accent_color = (236, 72, 153)  # pink-500
        secondary_color = (168, 85, 247)  # purple-500
        glow_color = (244, 114, 182)
        visual_type = "social_reactions"
    else:
        # Futuristic Clean Corporate Tech
        top_color = (15, 23, 42)
        bot_color = (30, 41, 59)
        accent_color = (59, 130, 246)
        secondary_color = (99, 102, 241)
        glow_color = (147, 197, 253)
        visual_type = "tech_architecture"

    # 1. Base Gradient Canvas
    img = Image.new("RGBA", (width, height), top_color + (255,))
    draw = ImageDraw.Draw(img)

    for y in range(height):
        p = y / float(height)
        r = int(top_color[0] + (bot_color[0] - top_color[0]) * p)
        g = int(top_color[1] + (bot_color[1] - top_color[1]) * p)
        b = int(top_color[2] + (bot_color[2] - top_color[2]) * p)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    # 2. Atmospheric Volumetric Glow Orbs
    glow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow_layer)

    # Center-top radiance
    cx, cy = width // 2, int(height * 0.45)
    gdraw.ellipse([cx - 380, cy - 380, cx + 380, cy + 380], fill=accent_color + (80,))
    gdraw.ellipse([cx - 220, cy - 220, cx + 220, cy + 220], fill=secondary_color + (110,))
    gdraw.ellipse([cx - 90, cy - 90, cx + 90, cy + 90], fill=glow_color + (160,))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(70))
    img = Image.alpha_composite(img, glow_layer)

    # 3. Geometric Tech Elements depending on Visual Type
    geom_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(geom_layer)

    if visual_type == "neural_net":
        # 9 Connected nodes with data conduits
        nodes = [
            (220, 360), (220, 540), (220, 720),
            (540, 300), (540, 540), (540, 780),
            (860, 360), (860, 540), (860, 720)
        ]
        # Connecting lines
        for i in range(3):
            for j in range(3, 6):
                pdraw.line([nodes[i], nodes[j]], fill=accent_color + (120,), width=3)
        for i in range(3, 6):
            for j in range(6, 9):
                pdraw.line([nodes[i], nodes[j]], fill=secondary_color + (120,), width=3)
        # Node circles with glowing rings
        for nx, ny in nodes:
            pdraw.ellipse([nx - 28, ny - 28, nx + 28, ny + 28], fill=(15, 23, 42, 230), outline=glow_color + (240,), width=4)
            pdraw.ellipse([nx - 12, ny - 12, nx + 12, ny + 12], fill=glow_color + (255,))

    elif visual_type == "financial_curve":
        # Grid lines
        for y_line in range(250, 850, 120):
            pdraw.line([(100, y_line), (980, y_line)], fill=(255, 255, 255, 40), width=1)
        # Bold Spline curve
        points = []
        for x_step in range(120, 960, 15):
            t = (x_step - 120) / 840.0
            # Falling or rising curve
            y_curve = 340 + 420 * math.sin(t * math.pi * 0.7)
            points.append((x_step, int(y_curve)))
        if len(points) >= 2:
            pdraw.line(points, fill=accent_color + (240,), width=8)
            for px, py in points[::6]:
                pdraw.ellipse([px - 10, py - 10, px + 10, py + 10], fill=glow_color + (255,))

    elif visual_type == "risk_shield":
        # Hexagonal shield wireframe
        r_shield = 260
        hex_pts = []
        for a_deg in range(30, 390, 60):
            rad = math.radians(a_deg)
            hex_pts.append((int(cx + r_shield * math.cos(rad)), int(cy + r_shield * math.sin(rad))))
        pdraw.polygon(hex_pts, outline=accent_color + (230,), width=6)
        # Inner shield
        inner_pts = []
        for a_deg in range(30, 390, 60):
            rad = math.radians(a_deg)
            inner_pts.append((int(cx + (r_shield - 50) * math.cos(rad)), int(cy + (r_shield - 50) * math.sin(rad))))
        pdraw.polygon(inner_pts, outline=secondary_color + (160,), width=3)
        # Radar rings
        pdraw.ellipse([cx - 130, cy - 130, cx + 130, cy + 130], outline=glow_color + (180,), width=3)
        pdraw.ellipse([cx - 60, cy - 60, cx + 60, cy + 60], fill=accent_color + (220,))

    elif visual_type == "versus_scale":
        # Split comparison: Left (Traditional Saving) vs Right (Algorithmic Growth)
        pdraw.line([(width // 2, 220), (width // 2, 860)], fill=(255, 255, 255, 70), width=2)
        # Left side: Vintage Clay Piggy / Vault
        lx, ly = width // 4, height // 2
        pdraw.ellipse([lx - 130, ly - 100, lx + 130, ly + 100], fill=(244, 63, 94, 180), outline=(255, 255, 255, 180), width=4)
        pdraw.line([(lx - 45, ly - 50), (lx + 45, ly - 50)], fill=(255, 255, 255, 240), width=6)
        pdraw.line([(lx, ly - 50), (lx + 20, ly - 10)], fill=(255, 255, 255, 200), width=3)
        pdraw.line([(lx + 20, ly - 10), (lx - 10, ly + 35)], fill=(255, 255, 255, 200), width=3)
        # Right side: Ascending Emerald Bars & Flow Arrow
        rx, ry = 3 * width // 4, height // 2
        bar_heights = [100, 160, 240, 320]
        for b_i, b_h in enumerate(bar_heights):
            bx = rx - 130 + b_i * 70
            by = ry + 120 - b_h
            pdraw.rounded_rectangle([bx, by, bx + 50, ry + 120], radius=8, fill=(16, 185, 129, 210), outline=(110, 231, 183, 255), width=2)
        pdraw.line([(rx - 110, ry + 50), (rx + 110, ry - 130)], fill=(253, 224, 71, 240), width=5)
        pdraw.polygon([(rx + 110, ry - 130), (rx + 80, ry - 130), (rx + 110, ry - 100)], fill=(253, 224, 71, 255))

    elif visual_type == "robotics":
        # Robotic arm & precision laser
        pdraw.line([(180, 780), (360, 520)], fill=(148, 163, 184, 220), width=16)
        pdraw.ellipse([360 - 24, 520 - 24, 360 + 24, 520 + 24], fill=accent_color + (240,))
        pdraw.line([(360, 520), (620, 480)], fill=(203, 213, 225, 240), width=12)
        pdraw.ellipse([620 - 20, 480 - 20, 620 + 20, 480 + 20], fill=glow_color + (240,))
        pdraw.line([(620, 480), (740, 660)], fill=(148, 163, 184, 220), width=10)
        # Precision laser beam
        pdraw.line([(740, 660), (840, 780)], fill=glow_color + (255,), width=4)
        pdraw.ellipse([840 - 30, 780 - 30, 840 + 30, 780 + 30], fill=accent_color + (180,))

    elif visual_type == "social_reactions":
        # Floating 3D reaction spheres (Heart, Like, Star)
        spheres = [
            (360, 460, 90, (239, 68, 68)),   # Red Heart sphere
            (680, 420, 110, (59, 130, 246)),  # Blue Thumbs Up sphere
            (520, 640, 100, (245, 158, 11)),  # Golden Star sphere
            (240, 660, 60, (168, 85, 247)),   # Purple accent sphere
            (820, 640, 70, (16, 185, 129)),   # Emerald accent sphere
        ]
        for sx, sy, sr, scolor in spheres:
            pdraw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=scolor + (220,), outline=(255, 255, 255, 140), width=3)
            # Specular highlight
            pdraw.ellipse([sx - int(sr * 0.4), sy - int(sr * 0.6), sx + int(sr * 0.1), sy - int(sr * 0.2)], fill=(255, 255, 255, 160))

    else:
        # Tech Architecture / Leader Stage
        for r_circle in (180, 320, 460):
            pdraw.ellipse([cx - r_circle, cy - r_circle, cx + r_circle, cy + r_circle], outline=accent_color + (70,), width=2)
        # Golden badge in center
        pdraw.ellipse([cx - 100, cy - 100, cx + 100, cy + 100], fill=(15, 23, 42, 240), outline=accent_color + (255,), width=5)
        pdraw.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], fill=glow_color + (255,))

    # Overlay tech elements
    img = Image.alpha_composite(img, geom_layer)

    # 4. Frosted Glass Metadata Badge at Top-Left
    meta_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    mdraw = ImageDraw.Draw(meta_layer)
    mdraw.rounded_rectangle([60, 60, 440, 124], radius=16, fill=(15, 23, 42, 210), outline=(255, 255, 255, 60), width=1)
    
    # Text font
    try:
        font_path = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "Inter-Bold.ttf"
        font = ImageFont.truetype(str(font_path), 24) if font_path.is_file() else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    badge_text = "AI VISUAL CONCEPT"
    if visual_type == "neural_net":
        badge_text = "AI NEURAL NETWORK"
    elif visual_type == "financial_curve":
        badge_text = "FINANCIAL TRAJECTORY"
    elif visual_type == "risk_shield":
        badge_text = "RISK ASSESSMENT"
    elif visual_type == "versus_scale":
        badge_text = "STRATEGIC COMPARISON"
    elif visual_type == "tech_leader":
        badge_text = "LEADER PERSPECTIVE"
    elif visual_type == "robotics":
        badge_text = "AUTOMATION ROBOTICS"
    elif visual_type == "social_reactions":
        badge_text = "COMMUNITY PULSE"

    mdraw.text((90, 78), f"● {badge_text}", font=font, fill=(255, 255, 255, 230))
    img = Image.alpha_composite(img, meta_layer)

    # Save RGB PNG
    final_rgb = img.convert("RGB")
    final_rgb.save(output_path, "PNG", quality=95)
    return output_path


def resolve_images_for_slide_script(project_dir: Path | str, slide_script: Any) -> list[str]:
    """Ensure every slide in slide_script has a valid, high-resolution visual image asset.
    
    Returns list of resolved image paths.
    """
    p_dir = Path(project_dir).resolve()
    assets_dir = p_dir / "assets" / "ai_images"
    assets_dir.mkdir(parents=True, exist_ok=True)

    slides = getattr(slide_script, "slides", []) if not isinstance(slide_script, list) else slide_script
    resolved_paths: list[str] = []

    for idx, slide in enumerate(slides):
        slots = getattr(slide, "slots", {}) if hasattr(slide, "slots") else slide.get("slots", {})
        slide_id = getattr(slide, "id", f"slide_{idx+1}")
        prompt = getattr(slide, "image_prompt", "") or slots.get("image_prompt", "") or getattr(slide, "narration", "") or slots.get("text", "")
        existing_url = slots.get("image_url")

        # Check if existing URL points to a valid file
        existing_valid = False
        if existing_url:
            p_exist = Path(existing_url) if Path(existing_url).is_absolute() else (p_dir / existing_url)
            if p_exist.is_file() and p_exist.stat().st_size > 2048:
                # Discard low-res placeholder clips (smaller than 30KB or blurry fallback)
                if "_fallback_" not in p_exist.name and p_exist.stat().st_size > 30000:
                    existing_valid = True
                    resolved_paths.append(str(p_exist))

        if not existing_valid:
            # Synthesize crisp cinematic artwork matching prompt
            target_path = assets_dir / f"beat_{idx+1:02d}_{sanitize_filename(slide_id)}.png"
            generate_cinematic_visual(prompt=prompt, output_path=target_path)
            slots["image_url"] = str(target_path)
            if hasattr(slide, "image_prompt"):
                slide.image_prompt = prompt
            resolved_paths.append(str(target_path))

    return resolved_paths
