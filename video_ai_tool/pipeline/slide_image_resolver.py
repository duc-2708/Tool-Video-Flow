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
import re
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
    Uses exact word boundaries so 'ai' substring never falsely matches 'portrait' or 'against'.
    """
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    p_low = prompt.lower()

    # Determine visual category with strict regex word boundaries
    if re.search(r"\b(singapore|sụt lún|settlement|geotechnical|sinkhole)\b", p_low):
        visual_type = "geotechnical_alert"
        top_color = (20, 24, 36)
        bot_color = (15, 30, 45)
        accent_color = (245, 158, 11)  # amber alert
        secondary_color = (14, 165, 233)  # cyber cyan
        glow_color = (252, 211, 77)

    elif re.search(r"\b(đường sắt|bắc nam|bắc - nam|1.541|1541|high-speed|railway|train)\b", p_low):
        visual_type = "high_speed_rail"
        top_color = (15, 23, 42)
        bot_color = (16, 40, 60)
        accent_color = (14, 165, 233)  # cyan transit
        secondary_color = (16, 185, 129)  # emerald track
        glow_color = (56, 189, 248)

    elif re.search(r"\b(tbm|cutterhead|tunnel boring|đào hầm|máy đào)\b", p_low):
        visual_type = "tbm_cutterhead"
        top_color = (15, 23, 42)
        bot_color = (30, 35, 45)
        accent_color = (234, 179, 8)  # industrial gold
        secondary_color = (239, 68, 68)  # industrial red
        glow_color = (250, 204, 21)

    elif re.search(r"\b(địa chất|soil strata|multi-layered|nhiều tầng|tường vây|diaphragm)\b", p_low):
        visual_type = "soil_strata"
        top_color = (18, 22, 30)
        bot_color = (35, 30, 25)
        accent_color = (217, 119, 6)  # earth amber
        secondary_color = (14, 165, 233)
        glow_color = (245, 158, 11)

    elif re.search(r"\b(kỹ sư|engineers|khảo sát|năng lực tổng hợp|làm chủ)\b", p_low):
        visual_type = "civil_engineers"
        top_color = (15, 23, 42)
        bot_color = (20, 35, 55)
        accent_color = (59, 130, 246)  # blue safety
        secondary_color = (234, 179, 8)  # gold helmet
        glow_color = (147, 197, 253)

    elif re.search(r"\b(elon|musk|speaker|keynote|founder|leader|ceo|dien gia|tac gia|portrait)\b", p_low):
        visual_type = "tech_leader"
        top_color = (15, 23, 42)
        bot_color = (30, 41, 59)
        accent_color = (234, 179, 8)  # warm gold
        secondary_color = (59, 130, 246)  # tech blue
        glow_color = (253, 224, 71)

    elif re.search(r"\b(piggy|heo dat|lon dat|tiet kiem|porcelain|escaping|coin)\b", p_low):
        visual_type = "piggy_savings"
        top_color = (26, 16, 32)
        bot_color = (48, 20, 40)
        accent_color = (244, 63, 94)  # rose coral
        secondary_color = (234, 179, 8)  # gold coins
        glow_color = (251, 113, 133)

    elif re.search(r"\b(robot|robotic|arm|welding|gigafactory|assembly|tay may|nha may)\b", p_low):
        visual_type = "robotics"
        top_color = (15, 23, 42)
        bot_color = (15, 35, 65)
        accent_color = (6, 182, 212)  # laser cyan
        secondary_color = (59, 130, 246)
        glow_color = (103, 232, 249)

    elif re.search(r"\b(candlestick|trading|terminal|market|spline|chung khoan|co phieu|giao dich)\b", p_low):
        visual_type = "candlestick_chart"
        top_color = (10, 20, 24)
        bot_color = (6, 50, 40)
        accent_color = (16, 185, 129)  # emerald-500
        secondary_color = (239, 68, 68)  # red-500
        glow_color = (110, 231, 183)

    elif re.search(r"\b(split|versus|dormant cash|productive|so sanh|doi dau|hai mat)\b", p_low):
        visual_type = "versus_split"
        top_color = (20, 20, 30)
        bot_color = (35, 25, 45)
        accent_color = (244, 63, 94)  # cash coral
        secondary_color = (16, 185, 129)  # asset emerald
        glow_color = (250, 204, 21)

    elif re.search(r"\b(quote|ted jenkin|article|clipping|journal|trich dan|bao chi|yahoo)\b", p_low):
        visual_type = "expert_quote"
        top_color = (15, 23, 42)
        bot_color = (24, 32, 47)
        accent_color = (56, 189, 248)  # sky
        secondary_color = (234, 179, 8)  # gold quote
        glow_color = (186, 230, 253)

    elif re.search(r"\b(emergency|reserve|gauge|speedometer|quy khan cap|du phong|ket sat)\b", p_low):
        visual_type = "emergency_fund"
        top_color = (12, 24, 30)
        bot_color = (10, 45, 55)
        accent_color = (16, 185, 129)  # safe green
        secondary_color = (234, 179, 8)  # vault gold
        glow_color = (52, 211, 153)

    elif re.search(r"\b(shield|security|deflect|risk|anomalies|khien|bao ve|rui ro)\b", p_low):
        visual_type = "risk_shield"
        top_color = (30, 15, 15)
        bot_color = (55, 20, 20)
        accent_color = (245, 158, 11)  # amber
        secondary_color = (239, 68, 68)  # crimson
        glow_color = (252, 211, 77)

    elif re.search(r"\b(balance|scale|equilibrium|can can|phan bo|ty trong)\b", p_low):
        visual_type = "wealth_balance"
        top_color = (20, 24, 36)
        bot_color = (32, 41, 58)
        accent_color = (234, 179, 8)  # gold scale
        secondary_color = (14, 165, 233)
        glow_color = (253, 224, 71)

    elif re.search(r"\b(key|cashflow|master key|pedestal|chia khoa|dong tien)\b", p_low):
        visual_type = "golden_key"
        top_color = (15, 23, 42)
        bot_color = (26, 36, 60)
        accent_color = (234, 179, 8)  # golden key
        secondary_color = (56, 189, 248)  # circuit cyan
        glow_color = (250, 204, 21)

    elif re.search(r"\b(creator|studio|reaction|sphere|follow|subscribe|kenh|tim|like)\b", p_low):
        visual_type = "social_reactions"
        top_color = (26, 16, 45)
        bot_color = (49, 20, 77)
        accent_color = (236, 72, 153)  # pink
        secondary_color = (168, 85, 247)  # purple
        glow_color = (244, 114, 182)

    elif re.search(r"\b(city|skyline|horizon|humanoid|do thi|tuong lai)\b", p_low):
        visual_type = "future_ai"
        top_color = (10, 15, 30)
        bot_color = (20, 30, 60)
        accent_color = (14, 165, 233)
        secondary_color = (168, 85, 247)
        glow_color = (56, 189, 248)

    else:
        # Neural Network core only when explicitly requested
        visual_type = "neural_net"
        top_color = (11, 15, 30)
        bot_color = (15, 23, 42)
        accent_color = (14, 165, 233)
        secondary_color = (99, 102, 241)
        glow_color = (56, 189, 248)

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

    cx, cy = width // 2, int(height * 0.48)
    gdraw.ellipse([cx - 400, cy - 400, cx + 400, cy + 400], fill=accent_color + (70,))
    gdraw.ellipse([cx - 240, cy - 240, cx + 240, cy + 240], fill=secondary_color + (100,))
    gdraw.ellipse([cx - 100, cy - 100, cx + 100, cy + 100], fill=glow_color + (160,))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(75))
    img = Image.alpha_composite(img, glow_layer)

    # 3. High-Detail Geometric Artwork Layer
    geom_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(geom_layer)

    if visual_type == "tech_leader":
        # Keynote stage spotlight & Elon Musk silhouette
        # Background keynote projection display
        pdraw.rounded_rectangle([180, 200, 900, 620], radius=24, fill=(15, 23, 42, 210), outline=accent_color + (140,), width=3)
        pdraw.line([(220, 260), (440, 260)], fill=glow_color + (240,), width=8)
        pdraw.line([(220, 300), (860, 300)], fill=(255, 255, 255, 60), width=2)
        # Miniature keynote charts inside display
        pdraw.rectangle([240, 350, 460, 560], fill=(30, 41, 59, 180), outline=(56, 189, 248, 180), width=2)
        pdraw.rectangle([500, 350, 840, 560], fill=(30, 41, 59, 180), outline=(234, 179, 8, 180), width=2)
        # Elon Musk keynote silhouette in foreground
        pdraw.ellipse([cx - 80, cy + 20, cx + 80, cy + 180], fill=(11, 15, 25, 250), outline=accent_color + (255,), width=4)
        pdraw.polygon([(cx - 160, cy + 340), (cx - 70, cy + 180), (cx + 70, cy + 180), (cx + 160, cy + 340)], fill=(11, 15, 25, 255), outline=accent_color + (200,))
        # Microphone stand & golden speech glow
        pdraw.line([(cx + 90, cy + 120), (cx + 90, cy + 350)], fill=(148, 163, 184, 255), width=6)
        pdraw.ellipse([cx + 80, cy + 100, cx + 100, cy + 125], fill=accent_color + (255,))

    elif visual_type == "piggy_savings":
        # 3D Porcelain Piggy Bank with golden cracks and coin fountain
        px, py = cx, cy + 30
        # Main Piggy Body
        pdraw.ellipse([px - 220, py - 160, px + 180, py + 160], fill=(244, 63, 94, 235), outline=(255, 255, 255, 200), width=6)
        # Snout
        pdraw.ellipse([px - 280, py - 60, px - 200, py + 60], fill=(251, 113, 133, 255), outline=(255, 255, 255, 220), width=4)
        pdraw.ellipse([px - 260, py - 20, px - 245, py + 20], fill=(15, 23, 42, 220))
        pdraw.ellipse([px - 235, py - 20, px - 220, py + 20], fill=(15, 23, 42, 220))
        # Ear
        pdraw.polygon([(px - 140, py - 150), (px - 170, py - 250), (px - 80, py - 180)], fill=(244, 63, 94, 255), outline=(255, 255, 255, 200))
        # Glowing Golden Cracks
        crack_points = [(px - 20, py - 160), (px + 10, py - 60), (px - 30, py + 20), (px + 40, py + 100), (px + 80, py + 160)]
        pdraw.line(crack_points, fill=glow_color + (255,), width=8)
        # Escaping Gold Coins
        coins = [(px + 40, py - 240, 36), (px + 110, py - 200, 32), (px + 180, py - 260, 42), (px + 240, py - 180, 28), (px + 150, py - 120, 30)]
        for cox, coy, cr in coins:
            pdraw.ellipse([cox - cr, coy - cr, cox + cr, coy + cr], fill=(234, 179, 8, 255), outline=(255, 255, 255, 240), width=4)
            pdraw.ellipse([cox - cr + 8, coy - cr + 8, cox + cr - 8, coy + cr - 8], fill=(250, 204, 21, 255))

    elif visual_type == "robotics":
        # Tesla Gigafactory high-precision robotic arm
        base_x, base_y = 200, 780
        elbow_x, elbow_y = 420, 500
        wrist_x, wrist_y = 680, 440
        tool_x, tool_y = 820, 620
        # Arm Segments
        pdraw.line([(base_x, base_y), (elbow_x, elbow_y)], fill=(148, 163, 184, 255), width=24)
        pdraw.ellipse([elbow_x - 34, elbow_y - 34, elbow_x + 34, elbow_y + 34], fill=accent_color + (255,))
        pdraw.line([(elbow_x, elbow_y), (wrist_x, wrist_y)], fill=(203, 213, 225, 255), width=18)
        pdraw.ellipse([wrist_x - 28, wrist_y - 28, wrist_x + 28, wrist_y + 28], fill=glow_color + (255,))
        pdraw.line([(wrist_x, wrist_y), (tool_x, tool_y)], fill=(148, 163, 184, 255), width=14)
        # Laser welding beam & sparks
        pdraw.line([(tool_x, tool_y), (880, 760)], fill=(56, 189, 248, 255), width=6)
        pdraw.ellipse([880 - 40, 760 - 40, 880 + 40, 760 + 40], fill=(253, 224, 71, 230))
        # Microchip circuit wafer beneath
        pdraw.rounded_rectangle([720, 740, 980, 840], radius=16, fill=(15, 23, 42, 240), outline=accent_color + (220,), width=3)
        pdraw.line([(760, 790), (940, 790)], fill=glow_color + (240,), width=4)

    elif visual_type == "candlestick_chart":
        # Bloomberg/TradingView Candlestick Terminal
        # Grid lines
        for y_g in range(240, 840, 100):
            pdraw.line([(140, y_g), (940, y_g)], fill=(255, 255, 255, 30), width=1)
        # Candlestick bars (x, open, high, low, close)
        candles = [
            (200, 680, 720, 600, 630, True),
            (280, 630, 660, 520, 540, True),
            (360, 540, 590, 530, 580, False),
            (440, 580, 620, 460, 480, True),
            (520, 480, 510, 400, 420, True),
            (600, 420, 460, 410, 450, False),
            (680, 450, 490, 340, 360, True),
            (760, 360, 380, 280, 300, True),
            (840, 300, 330, 220, 240, True),
        ]
        for cx_c, op, hi, lo, cl, is_up in candles:
            c_color = (16, 185, 129) if is_up else (239, 68, 68)
            # Wick
            pdraw.line([(cx_c, lo), (cx_c, hi)], fill=c_color + (220,), width=3)
            # Real Body
            top_b, bot_b = min(op, cl), max(op, cl)
            pdraw.rounded_rectangle([cx_c - 20, top_b, cx_c + 20, bot_b], radius=4, fill=c_color + (240,), outline=(255, 255, 255, 180), width=2)
        # Exponential moving average spline
        ma_points = [(c[0], (c[1] + c[4]) // 2) for c in candles]
        pdraw.line(ma_points, fill=(250, 204, 21, 250), width=5)

    elif visual_type == "versus_split":
        # Split comparison: Left (Cash Lockbox) vs Right (Microchip Capital)
        pdraw.line([(width // 2, 200), (width // 2, 880)], fill=(255, 255, 255, 60), width=3)
        # Left (Cash Lockbox on Red)
        lx, ly = width // 4, cy
        pdraw.rounded_rectangle([lx - 160, ly - 140, lx + 160, ly + 140], radius=20, fill=(244, 63, 94, 160), outline=(255, 255, 255, 160), width=3)
        pdraw.rectangle([lx - 80, ly - 40, lx + 80, ly + 40], fill=(30, 41, 59, 240), outline=(255, 255, 255, 200), width=3)
        pdraw.ellipse([lx - 16, ly - 16, lx + 16, ly + 16], fill=(244, 63, 94, 255))
        # Right (Productive Quantum Chip on Green)
        rx, ry = 3 * width // 4, cy
        pdraw.rounded_rectangle([rx - 160, ry - 140, rx + 160, ry + 140], radius=20, fill=(16, 185, 129, 160), outline=(110, 231, 183, 240), width=3)
        # Chip core
        pdraw.rectangle([rx - 70, ry - 70, rx + 70, ry + 70], fill=(15, 23, 42, 240), outline=(52, 211, 153, 255), width=4)
        for i_pin in range(-50, 60, 25):
            pdraw.line([(rx + i_pin, ry - 100), (rx + i_pin, ry - 70)], fill=(250, 204, 21, 240), width=4)
            pdraw.line([(rx + i_pin, ry + 70), (rx + i_pin, ry + 100)], fill=(250, 204, 21, 240), width=4)

    elif visual_type == "expert_quote":
        # Financial Press Article & Ted Jenkin Quotation
        pdraw.rounded_rectangle([160, 220, 920, 840], radius=28, fill=(15, 23, 42, 230), outline=(255, 255, 255, 80), width=2)
        # Newspaper Header
        pdraw.rounded_rectangle([200, 260, 480, 310], radius=8, fill=(56, 189, 248, 220))
        pdraw.line([(200, 340), (880, 340)], fill=(255, 255, 255, 40), width=2)
        # Giant Golden Quotation Marks
        pdraw.ellipse([220, 380, 280, 440], fill=(234, 179, 8, 255))
        pdraw.polygon([(220, 420), (200, 480), (250, 440)], fill=(234, 179, 8, 255))
        pdraw.ellipse([310, 380, 370, 440], fill=(234, 179, 8, 255))
        pdraw.polygon([(310, 420), (290, 480), (340, 440)], fill=(234, 179, 8, 255))
        # Article text lines
        for y_t in range(520, 760, 50):
            pdraw.line([(220, y_t), (860, y_t)], fill=(255, 255, 255, 120), width=6)

    elif visual_type == "emergency_fund":
        # Circular Emergency Reserve Gauge & Vault
        gx, gy = cx, cy
        # Outer Gauge Arc
        pdraw.arc([gx - 260, gy - 260, gx + 260, gy + 260], start=140, end=400, fill=(255, 255, 255, 60), width=30)
        pdraw.arc([gx - 260, gy - 260, gx + 260, gy + 260], start=220, end=380, fill=(16, 185, 129, 255), width=32)
        # Central Vault Wheel
        pdraw.ellipse([gx - 130, gy - 130, gx + 130, gy + 130], fill=(15, 23, 42, 240), outline=accent_color + (255,), width=8)
        for a_deg in range(0, 360, 45):
            rad = math.radians(a_deg)
            pdraw.line([(gx, gy), (int(gx + 120 * math.cos(rad)), int(gy + 120 * math.sin(rad)))], fill=(234, 179, 8, 220), width=6)
        pdraw.ellipse([gx - 45, gy - 45, gx + 45, gy + 45], fill=glow_color + (255,))

    elif visual_type == "risk_shield":
        # Hexagonal Cyber Shield
        r_shield = 280
        hex_pts = []
        for a_deg in range(30, 390, 60):
            rad = math.radians(a_deg)
            hex_pts.append((int(cx + r_shield * math.cos(rad)), int(cy + r_shield * math.sin(rad))))
        pdraw.polygon(hex_pts, outline=accent_color + (240,), width=8)
        inner_pts = []
        for a_deg in range(30, 390, 60):
            rad = math.radians(a_deg)
            inner_pts.append((int(cx + (r_shield - 50) * math.cos(rad)), int(cy + (r_shield - 50) * math.sin(rad))))
        pdraw.polygon(inner_pts, outline=secondary_color + (180,), width=4)
        pdraw.ellipse([cx - 140, cy - 140, cx + 140, cy + 140], outline=glow_color + (200,), width=4)
        pdraw.ellipse([cx - 60, cy - 60, cx + 60, cy + 60], fill=accent_color + (240,))

    elif visual_type == "wealth_balance":
        # Golden Mechanical Balance Scale
        pdraw.line([(cx, cy - 240), (cx, cy + 240)], fill=(234, 179, 8, 255), width=14)
        pdraw.line([(cx - 260, cy - 160), (cx + 260, cy - 160)], fill=(234, 179, 8, 255), width=10)
        # Left Pan (Gold Bullion)
        pdraw.line([(cx - 240, cy - 160), (cx - 240, cy)], fill=(255, 255, 255, 180), width=3)
        pdraw.arc([cx - 320, cy - 40, cx - 160, cy + 120], start=0, end=180, fill=(234, 179, 8, 255), width=6)
        pdraw.rectangle([cx - 280, cy, cx - 200, cy + 50], fill=(250, 204, 21, 255))
        # Right Pan (Algorithm Tokens)
        pdraw.line([(cx + 240, cy - 160), (cx + 240, cy - 20)], fill=(255, 255, 255, 180), width=3)
        pdraw.arc([cx + 160, cy - 60, cx + 320, cy + 100], start=0, end=180, fill=(234, 179, 8, 255), width=6)
        pdraw.ellipse([cx + 210, cy - 20, cx + 270, cy + 40], fill=(16, 185, 129, 255))

    elif visual_type == "golden_key":
        # Glowing 3D Golden Key on Glass Pedestal
        pdraw.ellipse([cx - 300, cy + 200, cx + 300, cy + 300], fill=(15, 23, 42, 220), outline=(56, 189, 248, 200), width=4)
        # Key Head Ring
        kx, ky = cx, cy - 50
        pdraw.ellipse([kx - 100, ky - 180, kx + 100, ky + 20], fill=(234, 179, 8, 255), outline=(255, 255, 255, 240), width=6)
        pdraw.ellipse([kx - 45, ky - 125, kx + 45, ky - 35], fill=(15, 23, 42, 255))
        # Key Shaft
        pdraw.line([(kx, ky + 20), (kx, ky + 220)], fill=(234, 179, 8, 255), width=24)
        # Key Teeth
        pdraw.rectangle([kx, ky + 140, kx + 70, ky + 175], fill=(234, 179, 8, 255))
        pdraw.rectangle([kx, ky + 190, kx + 90, ky + 220], fill=(234, 179, 8, 255))

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
            pdraw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=scolor + (220,), outline=(255, 255, 255, 160), width=4)
            pdraw.ellipse([sx - int(sr * 0.4), sy - int(sr * 0.6), sx + int(sr * 0.1), sy - int(sr * 0.2)], fill=(255, 255, 255, 180))

    elif visual_type == "geotechnical_alert":
        # Draw concentric radar telemetry rings and sensor nodes
        for r in (120, 220, 320):
            pdraw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=accent_color + (140,), width=3)
        # Warning sensor alerts
        pdraw.polygon([(cx, cy - 140), (cx + 120, cy + 80), (cx - 120, cy + 80)], fill=(245, 158, 11, 200), outline=(255, 255, 255, 240))
        pdraw.rectangle([cx - 8, cy - 80, cx + 8, cy - 10], fill=(15, 23, 42, 255))
        pdraw.ellipse([cx - 8, cy + 15, cx + 8, cy + 31], fill=(15, 23, 42, 255))

    elif visual_type == "high_speed_rail":
        # Converging perspective tracks
        pdraw.polygon([(cx - 40, cy - 100), (cx + 40, cy - 100), (cx + 400, cy + 420), (cx - 400, cy + 420)], fill=(16, 40, 60, 200), outline=accent_color + (180,))
        pdraw.line([(cx - 30, cy - 100), (cx - 300, cy + 420)], fill=(255, 255, 255, 220), width=6)
        pdraw.line([(cx + 30, cy - 100), (cx + 300, cy + 420)], fill=(255, 255, 255, 220), width=6)
        for y_t in range(cy - 60, cy + 400, 45):
            w_tie = int(60 + (y_t - (cy - 100)) * 0.9)
            pdraw.line([(cx - w_tie, y_t), (cx + w_tie, y_t)], fill=secondary_color + (160,), width=4)

    elif visual_type == "tbm_cutterhead":
        # Circular TBM Cutterhead disk with radial arms and teeth
        pdraw.ellipse([cx - 260, cy - 260, cx + 260, cy + 260], fill=(24, 30, 42, 240), outline=accent_color + (220,), width=8)
        for ang in range(0, 360, 45):
            rad = math.radians(ang)
            x2 = cx + int(240 * math.cos(rad))
            y2 = cy + int(240 * math.sin(rad))
            pdraw.line([(cx, cy), (x2, y2)], fill=(255, 255, 255, 180), width=6)
            pdraw.ellipse([x2 - 16, y2 - 16, x2 + 16, y2 + 16], fill=(239, 68, 68, 240))
        pdraw.ellipse([cx - 70, cy - 70, cx + 70, cy + 70], fill=accent_color + (240,), outline=(255, 255, 255, 255), width=4)

    elif visual_type == "soil_strata":
        # Multi-layered soil strata and diaphragm wall
        strata_colors = [
            (35, 45, 60, 220),
            (45, 40, 30, 220),
            (30, 50, 45, 220),
            (50, 35, 25, 220),
        ]
        for i, sc in enumerate(strata_colors):
            y1 = cy - 200 + i * 110
            y2 = y1 + 110
            pdraw.rectangle([cx - 360, y1, cx + 360, y2], fill=sc, outline=(255, 255, 255, 60), width=1)
        pdraw.rectangle([cx - 40, cy - 220, cx + 40, cy + 240], fill=(14, 165, 233, 220), outline=(255, 255, 255, 240), width=4)

    elif visual_type == "civil_engineers":
        # Digital transit blueprint schematic with safety helmet symbol
        pdraw.rounded_rectangle([cx - 280, cy - 180, cx + 280, cy + 180], radius=24, fill=(15, 23, 42, 230), outline=(59, 130, 246, 200), width=4)
        for gx in range(cx - 240, cx + 260, 60):
            pdraw.line([(gx, cy - 160), (gx, cy + 160)], fill=(59, 130, 246, 70), width=1)
        for gy in range(cy - 140, cy + 160, 60):
            pdraw.line([(cx - 260, gy), (cx + 260, gy)], fill=(59, 130, 246, 70), width=1)
        pdraw.arc([cx - 90, cy - 100, cx + 90, cy + 60], start=180, end=360, fill=(234, 179, 8, 255), width=10)
        pdraw.line([(cx - 110, cy - 10), (cx + 110, cy - 10)], fill=(234, 179, 8, 255), width=10)

    else:
        # High-tech Cyber Network
        nodes = [
            (220, 360), (220, 540), (220, 720),
            (540, 300), (540, 540), (540, 780),
            (860, 360), (860, 540), (860, 720)
        ]
        for i in range(3):
            for j in range(3, 6):
                pdraw.line([nodes[i], nodes[j]], fill=accent_color + (140,), width=3)
        for i in range(3, 6):
            for j in range(6, 9):
                pdraw.line([nodes[i], nodes[j]], fill=secondary_color + (140,), width=3)
        for nx, ny in nodes:
            pdraw.ellipse([nx - 28, ny - 28, nx + 28, ny + 28], fill=(15, 23, 42, 230), outline=glow_color + (240,), width=4)
            pdraw.ellipse([nx - 12, ny - 12, nx + 12, ny + 12], fill=glow_color + (255,))

    # Overlay tech elements
    img = Image.alpha_composite(img, geom_layer)

    # 4. Frosted Glass Metadata Badge at Top-Left
    meta_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    mdraw = ImageDraw.Draw(meta_layer)
    mdraw.rounded_rectangle([60, 60, 480, 126], radius=16, fill=(15, 23, 42, 220), outline=(255, 255, 255, 70), width=1)
    
    try:
        font_path = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "Inter-Bold.ttf"
        font = ImageFont.truetype(str(font_path), 24) if font_path.is_file() else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    badge_map = {
        "geotechnical_alert": "GEOTECHNICAL MONITORING",
        "high_speed_rail": "HIGH-SPEED RAIL INFRASTRUCTURE",
        "tbm_cutterhead": "TBM URBAN EXCAVATION",
        "soil_strata": "URBAN GEOLOGY STRATA",
        "civil_engineers": "TRANSIT INFRASTRUCTURE",
        "tech_leader": "LEADER PERSPECTIVE",
        "piggy_savings": "SAVINGS DECONSTRUCTION",
        "robotics": "AUTOMATION ROBOTICS",
        "candlestick_chart": "FINANCIAL TRAJECTORY",
        "versus_split": "STRATEGIC COMPARISON",
        "expert_quote": "VERIFIED CITATION",
        "emergency_fund": "SAFETY BUFFER GAUGE",
        "risk_shield": "RISK ASSESSMENT",
        "wealth_balance": "WEALTH EQUILIBRIUM",
        "golden_key": "CASHFLOW PRINCIPLE",
        "future_ai": "FUTURE TECH HORIZON",
        "social_reactions": "COMMUNITY PULSE",
        "neural_net": "AI NEURAL NETWORK",
    }
    badge_text = badge_map.get(visual_type, "AI VISUAL CONCEPT")
    mdraw.text((90, 78), f"● {badge_text}", font=font, fill=(255, 255, 255, 240))
    img = Image.alpha_composite(img, meta_layer)

    # Save RGB PNG
    final_rgb = img.convert("RGB")
    final_rgb.save(output_path, "PNG", quality=95)
    return output_path


STOPWORDS_VI = {
    "các", "những", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín", "mười",
    "để", "và", "là", "của", "trong", "khi", "tại", "từ", "ở", "về", "có", "làm", "được", "bị",
    "do", "bởi", "ra", "vào", "lên", "xuống", "đầu", "như", "theo", "giúp", "rằng", "thì", "mà",
    "bằng", "hay", "hoặc", "tới", "đến", "qua", "sau", "trước", "cùng", "nhất", "rất", "quá",
    "tầm", "mức", "chủ", "hỏi", "nhận", "đặt", "tạo", "mang", "coi", "tính", "biết", "thấy",
    "khiến", "nhằm", "gồm", "thuộc", "cần", "phía", "vận", "độ", "bậc", "đằng", "này", "đó",
    "kia", "đây", "thế", "sao", "gì", "nào", "ai", "đâu", "nhiều", "ít", "tất", "cả", "mọi",
    "chỉ", "vẫn", "đang", "đã", "sẽ", "phải", "nên", "với", "cho", "lại", "thêm", "bớt",
    "khỏi", "ngay", "liền", "luôn", "nữa", "rồi", "xong", "chưa", "không", "chẳng", "hẳn",
    "thực", "sự", "việc", "cách", "quá_trình", "phương_án", "bước_đi", "ý_chính", "điều",
    "vấn_đề", "người", "ta", "mình", "chúng_tôi", "bạn", "họ", "nó", "chúng_ta", "chúng",
    "thực_hiện", "tiến_hành", "áp_dụng", "sử_dụng", "đưa_ra", "đạt_được", "bước", "điểm",
}

GENERIC_TECHNICAL_STOPWORDS_EN = {
    "system", "systems", "standard", "standards", "failure", "failures", "project", "projects",
    "technology", "technologies", "engineer", "engineers", "engineering", "experience", "experiences",
    "process", "processes", "method", "methods", "management", "development", "solution", "solutions",
    "issue", "issues", "problem", "problems", "challenge", "challenges", "result", "results",
    "report", "reports", "study", "studies", "analysis", "case", "cases", "data", "application",
    "work", "job", "field", "area", "phase", "step", "model", "concept", "plan", "operation",
    "activity", "level", "factor", "feature", "requirement", "practice", "overview", "lesson",
    "role", "background", "article", "news", "information", "detail", "summary", "construction",
    "implementation", "execution", "technique", "techniques", "structure", "structures",
    "modern", "new", "old", "key", "important", "future", "world", "national", "global",
    "high", "low", "great", "main", "major", "different", "general", "specific",
    "reality", "contractor", "adjustment", "accuracy", "precise", "layer", "layers", "complex",
    "comparison", "value", "unit", "demand", "require", "condition", "status", "stage"
}

GENERIC_TECHNICAL_STOPWORDS_VI = {
    "hệ thống", "tiêu chuẩn", "sự cố", "dự án", "công nghệ", "kỹ sư", "kinh nghiệm", "quá trình",
    "phương pháp", "quản lý", "phát triển", "giải pháp", "vấn đề", "thách thức", "kết quả",
    "báo cáo", "nghiên cứu", "phân tích", "trường hợp", "dữ liệu", "ứng dụng", "công việc",
    "lĩnh vực", "giai đoạn", "bước", "mô hình", "khái niệm", "kế hoạch", "vận hành", "hoạt động",
    "mức độ", "yếu tố", "tính năng", "yêu cầu", "thực tiễn", "thực tế", "tổng quan", "bài học", "năng lực",
    "vai trò", "thông tin", "chi tiết", "tóm tắt", "bài viết", "tin tức", "thi công", "xây dựng",
    "kỹ thuật", "kết cấu", "bước tiến", "thực hiện", "hiện đại", "mới", "cũ", "quan trọng",
    "tương lai", "thế giới", "quốc gia", "toàn cầu", "lớn", "nhỏ", "khác", "chung", "cụ thể",
    "bước đi", "ý chính", "phương án", "điểm nhìn", "tiêu điểm", "chi tiết", "nhà thầu", "điều chỉnh",
    "chính xác", "đan xen", "đòi hỏi", "nhiều", "tầng", "tầng đất", "nền đất", "phức tạp",
    "đối chiếu", "so sánh", "chỉ số", "giá trị", "đơn vị", "nội dung", "khả năng", "thời gian"
}

# Documents, schematics, textbook pages, patents, medical diagrams blacklist
DOCUMENT_SCHEMATIC_BLACKLIST = {
    "diagram", "patent", "anatomy", "illustration", "medical", "schematic", "page",
    "document", "pdf", "sketch", "paper", "scan", "textbook", "drawing", "graph",
    "chart", "infographic", "manuscript", "x-ray", "mri", "ct-scan", "ultrasound",
    "histology", "pathology", "surgical", "clinical", "eye", "retina", "skull",
    "brain scan", "organ", "cardiology", "neurology", "biology", "specimen"
}

STOPWORDS_EN = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by",
    "from", "up", "about", "into", "over", "after", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "this", "that", "these", "those",
    "it", "its", "they", "them", "their", "we", "us", "our", "you", "your", "he", "him", "his",
    "she", "her", "how", "what", "which", "who", "whom", "where", "when", "why", "all", "any",
    "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only",
    "own", "same", "so", "than", "too", "very", "can", "will", "just", "should", "now"
} | GENERIC_TECHNICAL_STOPWORDS_EN

STOPWORDS_VI_EXTENDED = set(STOPWORDS_VI)
for phrase in GENERIC_TECHNICAL_STOPWORDS_VI:
    for w in phrase.split():
        STOPWORDS_VI_EXTENDED.add(w)

PERSON_TAGS = {
    "person", "people", "man", "woman", "men", "women", "human", "humans",
    "politician", "politicians", "celebrity", "celebrities", "portrait", "portraits",
    "face", "faces", "headshot", "president", "prime minister", "minister", "senator",
    "spokesperson", "người", "chân dung", "gương mặt", "chính trị gia", "người nổi tiếng",
    "tổng thống", "thủ tướng", "bộ trưởng", "đại biểu"
}

FAMOUS_PERSON_NAMES = {
    "trump", "donald trump", "musk", "elon musk", "biden", "joe biden", "obama", "barack obama",
    "putin", "vladimir putin", "xi jinping", "tập cận bình", "macron", "modi", "scholz",
    "zuckerberg", "mark zuckerberg", "tim cook", "sam altman", "jensen huang"
}

STOCK_GENERIC_TECH_TAGS = {
    "chip", "microchip", "ai chip", "semiconductor", "processor", "cpu", "gpu",
    "robot", "robotics", "robotic arm", "industrial robot", "humanoid",
    "laptop", "keyboard", "computer keyboard", "technology background", "tech background",
    "motherboard", "circuit board", "abstract technology", "cyber network", "futuristic background",
    "vi mạch", "bán dẫn", "tay máy", "bàn phím"
}

GENUINE_TECH_ENTITIES = {
    "ai", "artificial intelligence", "trí tuệ nhân tạo", "mạng thần kinh", "neural",
    "chip", "microchip", "vi mạch", "bán dẫn", "semiconductor", "processor",
    "robot", "robotics", "tự động hóa", "automation", "humanoid", "thuật toán"
}

DEFAULT_DOMAIN_SYNONYMS: dict[str, list[str]] = {
    "đường ống": ["pipeline", "pipe", "pipes", "plumbing", "water pipe", "drainage"],
    "đường ống ngầm": ["underground pipeline", "underground pipe", "subsurface pipe"],
    "hầm": ["tunnel", "underground tunnel", "metro tunnel"],
    "đào hầm": ["tunnel excavation", "tunnel boring", "tbm"],
    "tbm": ["tunnel boring machine", "tbm", "cutterhead", "slurry tbm", "earth pressure balance"],
    "địa chất": ["geology", "geotechnical", "soil strata", "strata"],
    "địa kỹ thuật": ["geotechnical engineering", "geotechnical", "soil mechanics"],
    "sụt lún": ["settlement", "subsidence", "ground displacement"],
    "singapore": ["singapore metro", "singapore", "nicoll highway"],
    "tường vây": ["diaphragm wall", "slurry wall", "retaining wall"],
    "cọc khoan nhồi": ["bored pile", "drilled shaft", "foundation pile"],
    "đường sắt": ["railway", "railroad", "train", "high-speed rail"],
    "bắc nam": ["north south", "vietnam rail"],
    "phẫu thuật": ["surgery", "surgical", "operation", "surgeon"],
    "nội soi": ["endoscopy", "endoscopic", "laparoscopy", "laparoscopic"],
    "phẫu thuật nội soi": ["laparoscopic surgery", "endoscopy", "endoscopic surgery", "laparoscopy"],
    "y tế": ["medical", "hospital", "clinic", "healthcare"],
    "bác sĩ": ["doctor", "surgeon", "physician"],
    "đào đất": ["excavation", "digging", "earthmoving", "soil digging"],
    "trồng cây": ["tree planting", "planting trees", "gardening", "reforestation", "agriculture"],
    "đất": ["soil", "ground", "earth", "land"],
    "cây": ["tree", "trees", "plant", "plants"],
    "nông nghiệp": ["agriculture", "farming", "crop"],
    "chip": ["microchip", "semiconductor", "processor", "integrated circuit", "wafer"],
    "vi mạch": ["microchip", "semiconductor", "integrated circuit"],
    "bán dẫn": ["semiconductor", "silicon wafer", "fab"],
    "trí tuệ nhân tạo": ["artificial intelligence", "ai", "machine learning", "neural network"],
    "ai": ["artificial intelligence", "ai model", "neural network"],
    "robot": ["robot", "robotics", "robotic arm", "automation"],
    "năng suất": ["productivity", "output", "efficiency", "financial"],
    "tài chính": ["finance", "financial", "treasury", "banking"],
    "lãi suất": ["interest rate", "central bank", "federal reserve"],
    "lạm phát": ["inflation", "consumer price", "macroeconomics"],
    "chứng khoán": ["stock market", "trading", "equity", "wall street"],
}


def is_document_or_schematic_image(im_or_path: Path | Image.Image | bytes) -> tuple[bool, str]:
    """Detect document / schematic / book / patent / medical diagram images via local pixel measurement (no API).
    
    Rules:
    1. White/bright background ratio >= 60% (R,G,B all >= 225 or Luminance >= 225)
    2. High edge density >= 3.5% (printed text lines, technical blueprint schematics, line graphs)
    """
    try:
        from PIL import ImageFilter
        import numpy as np

        if isinstance(im_or_path, (str, Path)):
            p = Path(im_or_path)
            if not p.is_file() or p.stat().st_size == 0:
                return False, "file_missing"
            im = Image.open(str(p)).convert("RGB")
        elif isinstance(im_or_path, bytes):
            import io
            im = Image.open(io.BytesIO(im_or_path)).convert("RGB")
        elif isinstance(im_or_path, Image.Image):
            im = im_or_path.convert("RGB")
        else:
            return False, "invalid_image_type"

        arr = np.array(im)
        # Check white / near-white background pixels (R, G, B all >= 225)
        bright_mask = (arr[..., 0] >= 225) & (arr[..., 1] >= 225) & (arr[..., 2] >= 225)
        bright_ratio = float(np.mean(bright_mask))

        if bright_ratio >= 0.60:
            # Measure edge density on grayscale image
            gray = im.convert("L")
            edges = gray.filter(ImageFilter.FIND_EDGES)
            arr_edges = np.array(edges)
            edge_density = float(np.mean(arr_edges >= 35))
            if edge_density >= 0.035:
                return True, f"Tài liệu/sơ đồ/trang sách (nền sáng {bright_ratio:.1%}, mật độ cạnh {edge_density:.2%})"
        return False, "ok"
    except Exception as e:
        return False, f"error: {e}"


_YUNET_DETECTOR = None


def _get_face_detector():
    """Lazily load OpenCV FaceDetectorYN using local YuNet ONNX model (no API)."""
    global _YUNET_DETECTOR
    if _YUNET_DETECTOR is not None:
        return _YUNET_DETECTOR
    try:
        import cv2
        for cand in [
            Path(__file__).resolve().parent.parent / "assets" / "models" / "face_detection_yunet_2023mar.onnx",
            Path("assets/models/face_detection_yunet_2023mar.onnx").resolve(),
            Path("video_ai_tool/assets/models/face_detection_yunet_2023mar.onnx").resolve(),
        ]:
            if cand.is_file() and cand.stat().st_size > 10000:
                _YUNET_DETECTOR = cv2.FaceDetectorYN.create(str(cand), "", (320, 320), score_threshold=0.6)
                break
    except Exception:
        _YUNET_DETECTOR = None
    return _YUNET_DETECTOR


def detect_faces(im_or_path: Path | Image.Image | str | Any) -> tuple[int, list]:
    """Detect human faces locally using YuNet DNN (no API).
    Returns (face_count, faces_list).
    """
    try:
        import cv2
        import numpy as np

        detector = _get_face_detector()
        if detector is None:
            return 0, []

        if isinstance(im_or_path, (str, Path)):
            p = Path(im_or_path)
            if not p.is_file():
                return 0, []
            img = cv2.imread(str(p))
        elif isinstance(im_or_path, np.ndarray):
            img = im_or_path
        elif isinstance(im_or_path, Image.Image):
            arr = np.array(im_or_path.convert("RGB"))
            img = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        else:
            return 0, []

        if img is None or img.size == 0:
            return 0, []

        h, w = img.shape[:2]
        scale = 640.0 / max(w, h)
        new_w, new_h = max(16, int(w * scale)), max(16, int(h * scale))
        resized = cv2.resize(img, (new_w, new_h))
        detector.setInputSize((new_w, new_h))
        _, faces = detector.detect(resized)
        if faces is not None and len(faces) > 0:
            return len(faces), list(faces)
        return 0, []
    except Exception:
        return 0, []


def detect_text_slide_document(im_or_path: Path | Image.Image | str | Any) -> tuple[bool, int, str]:
    """Detect whether an image is a slide, presentation, document, table, paper page, or schematic.
    Uses local OpenCV MSER, brightness, and horizontal/vertical edge density (no API).
    Returns (is_text_heavy, text_boxes_count, reason_str).
    """
    try:
        import cv2
        import numpy as np

        if isinstance(im_or_path, (str, Path)):
            p = Path(im_or_path)
            if not p.is_file():
                return False, 0, "file_missing"
            img = cv2.imread(str(p))
        elif isinstance(im_or_path, np.ndarray):
            img = im_or_path
        elif isinstance(im_or_path, Image.Image):
            arr = np.array(im_or_path.convert("RGB"))
            img = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        else:
            return False, 0, "invalid_type"

        if img is None or img.size == 0:
            return False, 0, "cannot_read"

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 1. Background brightness ratio: fraction of bright/light grey pixels (>= 185)
        bright_mask = gray >= 185
        bright_ratio = float(np.mean(bright_mask))

        # 2. Text-sized connected components / MSER & contours
        mser = cv2.MSER_create()
        regions, _ = mser.detectRegions(gray)
        text_like_boxes = 0
        for p_region in regions:
            _, _, bw, bh = cv2.boundingRect(p_region)
            if 8 <= bh <= 80 and 4 <= bw <= 120 and 0.15 <= bw / float(bh) <= 4.0:
                text_like_boxes += 1

        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contour_boxes = 0
        for cnt in contours:
            _, _, cw, ch = cv2.boundingRect(cnt)
            if 6 <= ch <= 100 and 4 <= cw <= 150 and 0.1 <= cw / float(ch) <= 5.0:
                contour_boxes += 1
        text_like_boxes = max(text_like_boxes, contour_boxes)

        # 3. Horizontal and vertical edge density (Sobel)
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        h_v_edge_density = float(np.mean((np.abs(sobel_x) > 35) | (np.abs(sobel_y) > 35)))

        # 4. Morphological gradient for horizontal text lines
        kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 1))
        grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel_h)
        text_line_density = float(np.mean(grad > 40))

        reasons = []
        is_text_heavy = False

        if bright_ratio >= 0.45 and text_like_boxes >= 60:
            is_text_heavy = True
            reasons.append(f"bright_bg={bright_ratio:.1%} & mser_boxes={text_like_boxes}")
        elif bright_ratio >= 0.35 and text_like_boxes >= 160:
            is_text_heavy = True
            reasons.append(f"dense_mser_boxes={text_like_boxes} & bright_bg={bright_ratio:.1%}")
        elif text_like_boxes >= 1500:
            is_text_heavy = True
            reasons.append(f"massive_mser_boxes={text_like_boxes}")
        elif bright_ratio >= 0.55 and h_v_edge_density >= 0.04:
            is_text_heavy = True
            reasons.append(f"bright_bg={bright_ratio:.1%} & edge_density={h_v_edge_density:.2%}")
        elif text_line_density >= 0.08 and bright_ratio >= 0.40:
            is_text_heavy = True
            reasons.append(f"text_lines={text_line_density:.2%} & bright_bg={bright_ratio:.1%}")

        reason_str = "; ".join(reasons) if is_text_heavy else "natural_photo"
        return is_text_heavy, text_like_boxes, reason_str
    except Exception as e:
        return False, 0, f"error: {e}"


def extract_scene_entities(slide_text: str, headline: str = "", synonyms_map: dict[str, list[str]] | None = None) -> list[str]:
    """Extract substantive noun phrases, key entities and synonyms from slide text without stopwords."""
    combined = f"{headline} {slide_text}".lower()
    clean_text = re.sub(r"[^\w\s]", " ", combined)
    tokens = clean_text.split()
    
    entities: list[str] = []
    
    # 1. Multi-word phrases (2-grams, 3-grams) where not all tokens are generic stopwords
    for n in (3, 2):
        for i in range(len(tokens) - n + 1):
            gram_tokens = tokens[i:i + n]
            phrase = " ".join(gram_tokens)
            # Skip if whole phrase is in generic technical stoplist
            if phrase in GENERIC_TECHNICAL_STOPWORDS_VI or phrase in GENERIC_TECHNICAL_STOPWORDS_EN:
                continue
            # Ensure at least 1 token is a distinctive non-stopword
            if any(t not in STOPWORDS_VI_EXTENDED and t not in STOPWORDS_EN for t in gram_tokens):
                if len(phrase) >= 4 and phrase not in entities:
                    entities.append(phrase)
                    
    # 2. Single substantive words (len >= 4, not in extended stoplist)
    for t in tokens:
        if t not in STOPWORDS_VI_EXTENDED and t not in STOPWORDS_EN and len(t) >= 4:
            if t not in entities:
                entities.append(t)

    # 3. Add synonyms using strict word-boundary matching on combined text
    domain_map = dict(DEFAULT_DOMAIN_SYNONYMS)
    if synonyms_map:
        for k, v in synonyms_map.items():
            domain_map.setdefault(k.lower(), []).extend(v)

    expanded: list[str] = list(entities)
    for k_term, syn_list in domain_map.items():
        # Match only whole word/phrase boundaries in combined text
        if re.search(rf"\b{re.escape(k_term)}\b", combined, re.IGNORECASE):
            for syn in syn_list:
                syn_low = syn.lower()
                if (
                    syn_low not in expanded
                    and syn_low not in GENERIC_TECHNICAL_STOPWORDS_EN
                    and syn_low not in GENERIC_TECHNICAL_STOPWORDS_VI
                ):
                    expanded.append(syn_low)

    expanded.sort(key=lambda s: len(s), reverse=True)
    return expanded


def explain_image_relevance(
    slide_text: str,
    image_metadata: dict[str, Any] | str | None = None,
    prompt: str = "",
    synonyms_map: dict[str, list[str]] | None = None,
    headline: str = "",
) -> tuple[bool, dict[str, Any]]:
    """Explain and verify whether image metadata matches scene substantive entities (FAIL-CLOSED).
    
    Rules:
    1a. Only distinctive substantive entities (proper nouns, engineering terms: Singapore, TBM, tunnel, metro, etc.).
        Generic words (system, standard, failure, project, technology, engineer...) are in stoplist and do NOT count as matches.
    1b. Must match >= 2 distinctive entities/synonyms across metadata, OR >= 1 distinctive entity inside title or caption.
    1c. Reject documents / schematics / book pages / patents / medical diagrams:
        - Metadata blacklist: diagram, patent, anatomy, illustration, medical, schematic, page, document, pdf, etc.
    1d. Return exact match reason (entities, fields) for reporting.
    2. Prohibit real people unless name appears verbatim in slide narration.
    3. Prohibit stock generic tech unless scene is genuinely AI/chip/robot.
    """
    if image_metadata is None:
        return False, {"reason": "Metadata ảnh bị thiếu hoặc rỗng (fail-closed)"}

    meta_parts: list[str] = []
    title_caption_parts: list[str] = []
    field_map: dict[str, str] = {}

    if isinstance(image_metadata, dict):
        for k in ("title", "caption"):
            v = image_metadata.get(k)
            if v:
                title_caption_parts.append(str(v))
        for k in ("title", "alt", "tags", "caption", "description", "url", "source", "image"):
            val = image_metadata.get(k)
            if isinstance(val, list):
                s_val = " ".join(str(v) for v in val if v)
                meta_parts.append(s_val)
                field_map[k] = s_val
            elif val:
                s_val = str(val)
                meta_parts.append(s_val)
                field_map[k] = s_val
    elif isinstance(image_metadata, str):
        meta_parts.append(image_metadata)
        title_caption_parts.append(image_metadata)
        field_map["text"] = image_metadata
    else:
        return False, {"reason": "Kiểu dữ liệu metadata không hợp lệ"}

    if prompt:
        meta_parts.append(prompt)

    meta_text = " ".join(meta_parts).strip().lower()
    title_caption_text = " ".join(title_caption_parts).strip().lower()
    if not meta_text:
        return False, {"reason": "Nội dung metadata rỗng"}

    narr_low = slide_text.lower()
    head_low = headline.lower()
    scene_full = f"{narr_low} {head_low}"

    # RULE 2: Cấm ảnh có người thật trừ khi tên người đó xuất hiện nguyên văn trong narration
    for p_name in FAMOUS_PERSON_NAMES:
        if re.search(rf"\b{re.escape(p_name)}\b", meta_text):
            if not re.search(rf"\b{re.escape(p_name)}\b", narr_low):
                return False, {"reason": f"Chứa tên người nổi tiếng '{p_name}' không có trong lời đọc cảnh"}

    has_person_tag = any(re.search(rf"\b{re.escape(pt)}\b", meta_text) for pt in PERSON_TAGS)
    if has_person_tag:
        has_named_speaker = any(
            re.search(rf"\b{re.escape(n)}\b", narr_low)
            for n in ("ông", "bà", "tiến sĩ", "ts", "chuyên gia", "bác sĩ", "kỹ sư", "tác giả", "giám đốc")
        ) or any(re.search(rf"\b{re.escape(p)}\b", narr_low) for p in FAMOUS_PERSON_NAMES)
        if not has_named_speaker:
            return False, {"reason": "Chứa tag người thật nhưng lời đọc cảnh không nhắc đến nhân vật cụ thể"}

    # RULE 3: Cấm ảnh stock chung chung trừ khi chủ đề cảnh thật sự là AI/chip/robot
    scene_has_tech = any(re.search(rf"\b{re.escape(k)}\b", scene_full) for k in GENUINE_TECH_ENTITIES)
    has_generic_stock = any(re.search(rf"\b{re.escape(st)}\b", meta_text) for st in STOCK_GENERIC_TECH_TAGS)
    if has_generic_stock and not scene_has_tech:
        return False, {"reason": "Chứa ảnh stock công nghệ chung (chip, robot, laptop) trong khi cảnh không phải chủ đề AI/chip/robot"}

    # RULE 1c: Cấm ảnh dạng tài liệu/sơ đồ/trang sách/bằng sáng chế/ảnh y khoa
    for b_term in DOCUMENT_SCHEMATIC_BLACKLIST:
        if re.search(rf"\b{re.escape(b_term)}\b", meta_text):
            if b_term in ("medical", "surgical", "clinical"):
                is_medical_scene = any(k in scene_full for k in ("y tế", "bác sĩ", "phẫu thuật", "nội soi", "bệnh viện", "y khoa", "medical", "surgery"))
                if not is_medical_scene:
                    return False, {"reason": f"Chứa từ khóa y tế/y khoa bị cấm cho cảnh phi y tế: '{b_term}'"}
            else:
                if not re.search(rf"\b{re.escape(b_term)}\b", scene_full):
                    return False, {"reason": f"Chứa từ khóa tài liệu/sơ đồ/y khoa bị cấm: '{b_term}'"}

    # RULE 1a & 1b: Khớp thực thể đặc trưng của cảnh
    entities = extract_scene_entities(slide_text, headline, synonyms_map=synonyms_map)
    if not entities:
        return False, {"reason": "Không bóc tách được thực thể đặc trưng nào từ lời đọc cảnh"}

    matched_in_title_caption: list[str] = []
    matched_all: list[str] = []
    matched_fields: list[str] = []

    for ent in entities:
        ent_re = rf"\b{re.escape(ent)}\b"
        if re.search(ent_re, title_caption_text):
            if ent not in matched_in_title_caption:
                matched_in_title_caption.append(ent)
        if re.search(ent_re, meta_text):
            if ent not in matched_all:
                matched_all.append(ent)
            for f_name, f_val in field_map.items():
                if re.search(ent_re, f_val.lower()) and f_name not in matched_fields:
                    matched_fields.append(f_name)

    # Condition 1b: Phải khớp >= 2 thực thể/synonym đặc trưng, HOẶC >= 1 thực thể nằm trong title/caption của ảnh
    has_valid_match = (len(matched_in_title_caption) >= 1) or (len(matched_all) >= 2)
    if not has_valid_match:
        return False, {
            "reason": f"Chưa đạt ngưỡng khớp: khớp {len(matched_in_title_caption)} ở title/caption, {len(matched_all)} tổng cộng (yêu cầu >= 1 ở title/caption hoặc >= 2 ở toàn bộ metadata)",
            "matched_entities": matched_all,
            "matched_fields": matched_fields,
            "matched_in_title_caption": matched_in_title_caption,
        }

    return True, {
        "reason": f"Khớp thực thể '{', '.join(matched_all)}' ở trường {', '.join(matched_fields)}",
        "matched_entities": matched_all,
        "matched_fields": matched_fields,
        "matched_in_title_caption": matched_in_title_caption,
    }


def check_image_relevance(
    slide_text: str,
    image_metadata: dict[str, Any] | str | None = None,
    prompt: str = "",
    synonyms_map: dict[str, list[str]] | None = None,
    headline: str = "",
) -> bool:
    """Verify that actual image metadata matches scene substantive entities (FAIL-CLOSED)."""
    is_rel, _ = explain_image_relevance(
        slide_text=slide_text,
        image_metadata=image_metadata,
        prompt=prompt,
        synonyms_map=synonyms_map,
        headline=headline,
    )
    return is_rel


def _query_for_beat(idx: int, prompt: str, narration: str = "", headline: str = "") -> str:
    """Determine authentic search query for given beat based on scene entities without hardcoding."""
    entities = extract_scene_entities(narration, headline)
    clean_words = [
        w for w in re.findall(r"\b[a-zA-Z]{3,}\b", prompt)
        if w.lower() not in {
            "cinematic", "photorealistic", "ultra", "dramatic", "concept", "render",
            "detailed", "hyper", "lighting", "ambient", "depth", "field", "octane", "volumetric"
        }
    ]
    # Filter English-friendly entities or Latin tokens
    latin_ents = [e for e in entities if re.match(r"^[a-zA-Z\s]+$", e)]
    top_ents = latin_ents[:2] if latin_ents else entities[:2]

    parts: list[str] = []
    for ent in top_ents:
        parts.append(ent)
    for cw in clean_words[:3]:
        if cw.lower() not in " ".join(parts).lower():
            parts.append(cw)

    q = " ".join(parts).strip()
    return q if len(q) >= 4 else "infrastructure technology"


def download_real_web_image(
    query: str,
    target_path: Path,
    slide_text: str = "",
    headline: str = "",
    synonyms_map: dict[str, list[str]] | None = None,
    timeout: float = 5.0,
    out_match_info: dict[str, Any] | None = None,
) -> bool:
    """Download an authentic high-resolution web photo with verified relevant metadata, center-crop to 1080x1080."""
    if not query:
        return False
    try:
        from ddgs import DDGS
        import requests
        import io
        
        ddgs = DDGS()
        results = list(ddgs.images(query, max_results=8))
        for r in results:
            if slide_text or headline:
                is_rel, match_info = explain_image_relevance(
                    slide_text=slide_text,
                    image_metadata=r,
                    synonyms_map=synonyms_map,
                    headline=headline,
                )
                if not is_rel:
                    continue
                if out_match_info is not None:
                    out_match_info.update(match_info)

            url = r.get("image")
            if not url or not url.startswith("http"):
                continue
            try:
                resp = requests.get(
                    url,
                    timeout=timeout,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                )
                if resp.status_code == 200 and len(resp.content) > 15000:
                    im = Image.open(io.BytesIO(resp.content)).convert("RGB")
                    w, h = im.size
                    if w < 250 or h < 250:
                        continue

                    # RULE 1c: Loại bỏ ảnh tài liệu/sơ đồ/trang sách/y khoa bằng đo pixel cục bộ
                    is_doc, doc_reason = is_document_or_schematic_image(im)
                    if is_doc:
                        continue

                    # RULE 1: Cổng phát hiện khuôn mặt cục bộ - loại nếu có >= 1 mặt mà không có tên trong lời đọc
                    narr_lower = f"{slide_text} {headline}".lower()
                    has_named_person = any(re.search(rf"\b{re.escape(p)}\b", narr_lower) for p in FAMOUS_PERSON_NAMES)
                    face_count, _ = detect_faces(im)
                    if face_count >= 1 and not has_named_person:
                        continue

                    # RULE 1: Cổng phát hiện chữ/slide/bảng/tài liệu cục bộ
                    is_text_heavy, mser_count, cv_reason = detect_text_slide_document(im)
                    if is_text_heavy:
                        continue

                    # Center crop to 1:1 square
                    min_dim = min(w, h)
                    left = (w - min_dim) // 2
                    top = (h - min_dim) // 2
                    im_crop = im.crop((left, top, left + min_dim, top + min_dim))
                    im_resized = im_crop.resize((1080, 1080), Image.Resampling.LANCZOS)
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    im_resized.save(target_path, "PNG")
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def resolve_images_for_slide_script(
    project_dir: Path | str,
    slide_script: Any,
    force_refresh: bool = True,
    allow_web_search: bool = True,
) -> list[str]:
    """Ensure every slide in slide_script has a valid, distinct visual image asset or large text.
    
    Guarantees every beat has a distinct visual:
    1. Relevance check (FAIL-CLOSED): real image metadata must match >= 1 slide entity.
    2. Zero duplicates: no image (hash) can appear > 1 time in video.
    3. Missing metadata or failed relevance -> NO image attached, falls back to typographic layout.
    4. Document/schematic/textbook/medical images rejected via local pixel measurement.
    5. Local CV face detection (YuNet) rejects faces without person name in narration.
    6. Local CV text/slide detection (MSER + brightness) rejects slide/table/document images.
    7. Match reason recorded for reporting.
    """
    p_dir = Path(project_dir).resolve()
    assets_dir = p_dir / "assets" / "ai_images"
    assets_dir.mkdir(parents=True, exist_ok=True)

    brief_data: dict[str, Any] = {}
    brief_file = p_dir / "brief.json"
    if brief_file.is_file():
        try:
            brief_data = json.loads(brief_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    from agents.photo_finder import PhotoFinder
    photo_finder = PhotoFinder(p_dir)

    if isinstance(slide_script, dict):
        slides = slide_script.get("slides", [])
    elif isinstance(slide_script, list):
        slides = slide_script
    else:
        slides = getattr(slide_script, "slides", [])
    resolved_paths: list[str] = []
    seen_image_hashes: set[str] = set()
    image_report: list[dict[str, Any]] = []

    for idx, slide in enumerate(slides):
        slots = getattr(slide, "slots", {}) if hasattr(slide, "slots") else slide.get("slots", {})
        slide_id = getattr(slide, "id", f"slide_{idx+1}")
        slide_narr = getattr(slide, "narration", "") or slots.get("text", "") or slots.get("title", "")
        headline = getattr(slide, "headline", "") or slots.get("headline", "") or slots.get("title", "")
        prompt = getattr(slide, "image_prompt", "") or slots.get("image_prompt", "") or slide_narr
        synonyms_map = getattr(slide, "synonyms_map", None) or slots.get("synonyms_map", None)

        scene_entities = extract_scene_entities(slide_narr, headline=headline, synonyms_map=synonyms_map)

        # 1. Try finding authentic photo via PhotoFinder (Wikidata person or Wikimedia Commons landmark/machine)
        photo_res = None
        if allow_web_search and photo_finder.resolved_count < 4:
            photo_res = photo_finder.find_photo_for_scene(
                slide_id=slide_id,
                narration=slide_narr,
                brief=brief_data,
                headline=headline,
                scene_entities=scene_entities,
            )

        if photo_res:
            p_path = Path(photo_res["image_path"])
            im_hash = hashlib.sha256(p_path.read_bytes()).hexdigest()
            if im_hash not in seen_image_hashes:
                seen_image_hashes.add(im_hash)
                slots["image_url"] = str(p_path)
                slots["path"] = str(p_path)
                slots["caption"] = photo_res.get("caption", "")
                slots["credit"] = photo_res.get("caption", "")
                slots["author"] = photo_res.get("author", "")
                if photo_res.get("name"):
                    slots["name"] = photo_res["name"]
                slots["photo"] = {
                    "path": str(p_path),
                    "caption": photo_res.get("caption", ""),
                    "author": photo_res.get("author", ""),
                    "license": photo_res.get("license", ""),
                }
                match_reason_str = photo_res.get("reason", "Khớp ảnh thật có bản quyền mở")
                slots["image_match_reason"] = match_reason_str

                cur_layout = getattr(slide, "layout", "kit_title") if hasattr(slide, "layout") else slide.get("layout", "kit_title")
                if cur_layout in ("kit_title", "kit_photo", "lg_note_card", "lg_source_headline"):
                    if hasattr(slide, "layout"):
                        slide.layout = "kit_photo"
                    elif isinstance(slide, dict):
                        slide["layout"] = "kit_photo"

                resolved_paths.append(str(p_path))
                image_report.append({
                    "slide_id": slide_id,
                    "attached": True,
                    "source": "Wikimedia Commons / Wikidata",
                    "image_path": str(p_path),
                    "caption": photo_res.get("caption", ""),
                    "license": photo_res.get("license", ""),
                    "reason": match_reason_str,
                    "face_count": 1 if photo_res.get("type") == "person" else 0,
                    "text_density": 0,
                    "entity_matched": [photo_res.get("entity", "")],
                })
                continue

        # 2. Check conceptual scene fallback via DDGS / web search
        narr_lower = f"{slide_narr} {headline}".lower()
        has_named_person = any(re.search(rf"\b{re.escape(p)}\b", narr_lower) for p in FAMOUS_PERSON_NAMES)
        is_concept_only = not has_named_person and not any(kw in narr_lower for kw in ("đường hầm", "metro", "singapore", "tbm", "ga ngầm", "cọc khoan", "tường vây"))

        q = _query_for_beat(idx, prompt, narration=slide_narr, headline=headline)
        target_path = assets_dir / f"beat_{idx+1:02d}_{sanitize_filename(slide_id)}.png"
        downloaded = False
        match_info: dict[str, Any] = {}

        if force_refresh:
            target_path.unlink(missing_ok=True)

        if allow_web_search and q and is_concept_only:
            downloaded = download_real_web_image(
                q,
                target_path,
                slide_text=slide_narr,
                headline=headline,
                synonyms_map=synonyms_map,
                out_match_info=match_info,
            )

        # FAIL-CLOSED: If not downloaded or no image with verified metadata -> DO NOT ATTACH IMAGE
        if downloaded and target_path.is_file() and target_path.stat().st_size > 0:
            narr_lower = f"{slide_narr} {headline}".lower()
            has_named_person = any(re.search(rf"\b{re.escape(p)}\b", narr_lower) for p in FAMOUS_PERSON_NAMES)
            face_cnt, _ = detect_faces(target_path)
            if face_cnt >= 1 and not has_named_person:
                target_path.unlink(missing_ok=True)
                slots.pop("image_url", None)
                slots.pop("photo", None)
                image_report.append({
                    "slide_id": slide_id,
                    "attached": False,
                    "source": q,
                    "reason": f"Bị loại vì phát hiện {face_cnt} khuôn mặt người thật mà không có tên trong lời đọc",
                    "face_count": face_cnt,
                    "text_density": 0,
                    "entity_matched": match_info.get("matched_entities", []),
                })
                continue

            is_slide_doc, mser_cnt, slide_doc_reason = detect_text_slide_document(target_path)
            if is_slide_doc:
                target_path.unlink(missing_ok=True)
                slots.pop("image_url", None)
                slots.pop("photo", None)
                image_report.append({
                    "slide_id": slide_id,
                    "attached": False,
                    "source": q,
                    "reason": f"Bị loại vì là ảnh slide/bảng/tài liệu ({slide_doc_reason})",
                    "face_count": face_cnt,
                    "text_density": mser_cnt,
                    "entity_matched": match_info.get("matched_entities", []),
                })
                continue

            is_doc, doc_reason = is_document_or_schematic_image(target_path)
            if is_doc:
                target_path.unlink(missing_ok=True)
                slots.pop("image_url", None)
                slots.pop("photo", None)
                image_report.append({
                    "slide_id": slide_id,
                    "attached": False,
                    "source": q,
                    "reason": f"Bị loại vì {doc_reason}",
                    "face_count": face_cnt,
                    "text_density": mser_cnt,
                    "entity_matched": match_info.get("matched_entities", []),
                })
                continue

            im_hash = hashlib.sha256(target_path.read_bytes()).hexdigest()
            if im_hash in seen_image_hashes:
                # Duplicate image hash! Remove and fall back to large text layout
                target_path.unlink(missing_ok=True)
                slots.pop("image_url", None)
                slots.pop("photo", None)
                image_report.append({
                    "slide_id": slide_id,
                    "attached": False,
                    "source": q,
                    "reason": "Trùng mã băm ảnh (duplicate hash) với cảnh trước đó",
                    "face_count": face_cnt,
                    "text_density": mser_cnt,
                    "entity_matched": match_info.get("matched_entities", []),
                })
            else:
                seen_image_hashes.add(im_hash)
                slots["image_url"] = str(target_path)
                match_reason_str = match_info.get("reason", "Khớp thực thể đặc trưng cảnh")
                slots["image_match_reason"] = match_reason_str
                if hasattr(slide, "image_prompt"):
                    slide.image_prompt = prompt
                resolved_paths.append(str(target_path))
                image_report.append({
                    "slide_id": slide_id,
                    "attached": True,
                    "source": q,
                    "image_path": str(target_path),
                    "reason": match_reason_str,
                    "face_count": face_cnt,
                    "text_density": mser_cnt,
                    "entity_matched": match_info.get("matched_entities", []),
                    "matched_fields": match_info.get("matched_fields", []),
                })
        else:
            target_path.unlink(missing_ok=True)
            slots.pop("image_url", None)
            slots.pop("photo", None)
            slots.pop("caption", None)
            if getattr(slide, "layout", "") == "kit_photo":
                if hasattr(slide, "layout"):
                    slide.layout = "kit_title"
                elif isinstance(slide, dict):
                    slide["layout"] = "kit_title"
            if "photo" in slots:
                slots["photo"] = None
            image_report.append({
                "slide_id": slide_id,
                "attached": False,
                "source": q,
                "reason": "Không tìm thấy ảnh thỏa mãn điều kiện khớp thực thể (dùng layout chữ lớn)",
                "face_count": 0,
                "text_density": 0,
                "entity_matched": [],
            })

    try:
        (p_dir / "image_relevance_report.json").write_text(
            json.dumps(image_report, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception:
        pass

    return resolved_paths
