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


def download_real_web_image(query: str, target_path: Path, timeout: float = 5.0) -> bool:
    """Download an authentic high-resolution web photo matching query, center-crop to 1080x1080."""
    if not query:
        return False
    try:
        from ddgs import DDGS
        import requests
        import io
        
        ddgs = DDGS()
        results = list(ddgs.images(query, max_results=5))
        for r in results:
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


def check_image_relevance(slide_text: str, query: str, prompt: str) -> bool:
    """Verify that image query/prompt contains >= 1 entity or primary keyword of the slide."""
    keywords = [
        "singapore", "sụt lún", "tbm", "địa chất", "đường sắt", "bắc nam",
        "tường vây", "quan trắc", "tiêu chuẩn", "kỹ sư", "metro", "hầm"
    ]
    txt_low = slide_text.lower()
    matched_keywords = [k for k in keywords if k in txt_low]
    if not matched_keywords:
        return True
    qp = f"{query} {prompt}".lower()
    return any(k in qp for k in matched_keywords)


def _query_for_beat(idx: int, prompt: str, narration: str = "") -> str:
    """Determine authentic search query for given beat and prompt based on content keywords."""
    combined = f"{prompt} {narration}".lower()
    if any(k in combined for k in ("singapore", "sụt lún", "nicoll")):
        return "Singapore metro underground tunnel construction geotechnical engineering"
    elif any(k in combined for k in ("đường sắt", "bắc nam", "bắc - nam", "1.541", "1541", "tốc độ cao")):
        return "high speed railway passenger train construction viaduct infrastructure"
    elif any(k in combined for k in ("tbm", "đào hầm", "máy đào hầm")):
        return "Tunnel Boring Machine TBM underground metro construction cutterhead"
    elif any(k in combined for k in ("tường vây", "địa chất", "nhiều tầng", "đất đá")):
        return "diaphragm wall deep foundation geotechnical engineering urban construction"
    elif any(k in combined for k in ("quan sát", "quan trắc", "cảm biến", "chướng ngại vật")):
        return "geotechnical monitoring sensors tunnel displacement instrumentation"
    elif any(k in combined for k in ("tiêu chuẩn", "ngôn ngữ chung", "khung kỹ thuật")):
        return "civil engineering blueprint technical specification construction standards"
    elif any(k in combined for k in ("kỹ sư", "làm chủ", "khảo sát", "năng lực tổng hợp")):
        return "Vietnamese civil engineers infrastructure tunnel construction project"
    elif any(k in combined for k in ("hầm", "công trình ngầm", "lòng đất", "địa đạo")):
        return "underground tunnel construction engineering urban infrastructure"
    elif any(k in combined for k in ("elon musk",)):
        return "Elon Musk speaking stage keynote conference portrait"
    elif any(k in combined for k in ("heo đất", "lợn đất", "piggy bank")):
        return "piggy bank breaking shattered money cash savings"
    elif any(k in combined for k in ("robot", "gigafactory", "tay máy")):
        return "industrial robot automation manufacturing factory"
    elif any(k in combined for k in ("chip", "vi mạch", "bán dẫn")):
        return "ai microchip processor semiconductor hardware technology"
    elif any(k in combined for k in ("ted jenkin",)):
        return "Ted Jenkin financial advisor portrait"
    elif any(k in combined for k in ("khiên", "an ninh", "bảo mật")):
        return "cyber security shield digital protection network technology"
    elif any(k in combined for k in ("kênh", "youtube", "subscribe", "đăng ký", "theo dõi")):
        return "modern digital broadcast studio newsroom"

    clean_words = [w for w in re.findall(r"\b[a-zA-Z]{3,}\b", prompt) if w.lower() not in {"cinematic", "photorealistic", "ultra", "dramatic", "concept", "render"}]
    if clean_words:
        return " ".join(clean_words[:4]) + " engineering infrastructure"
    return "modern engineering technology infrastructure"


def resolve_images_for_slide_script(
    project_dir: Path | str,
    slide_script: Any,
    force_refresh: bool = True,
    allow_web_search: bool = True,
) -> list[str]:
    """Ensure every slide in slide_script has a valid, distinct visual image asset or large text.
    
    Guarantees every beat has a distinct visual:
    1. Relevance check: image query/prompt must match >= 1 slide entity/keyword.
    2. Zero duplicates: no image (hash) can appear > 1 time in video.
    3. Fails check -> uses clean typographic large-text layout (no image attached).
    """
    p_dir = Path(project_dir).resolve()
    assets_dir = p_dir / "assets" / "ai_images"
    assets_dir.mkdir(parents=True, exist_ok=True)

    slides = getattr(slide_script, "slides", []) if not isinstance(slide_script, list) else slide_script
    resolved_paths: list[str] = []
    seen_image_hashes: set[str] = set()

    for idx, slide in enumerate(slides):
        slots = getattr(slide, "slots", {}) if hasattr(slide, "slots") else slide.get("slots", {})
        slide_id = getattr(slide, "id", f"slide_{idx+1}")
        slide_narr = getattr(slide, "narration", "") or slots.get("text", "") or slots.get("title", "")
        prompt = getattr(slide, "image_prompt", "") or slots.get("image_prompt", "") or slide_narr

        q = _query_for_beat(idx, prompt, narration=slide_narr)

        # Relevance check
        is_relevant = check_image_relevance(slide_narr, q, prompt)
        if not is_relevant:
            # Fails relevance: scene uses large text layout, NO image attached
            slots.pop("image_url", None)
            slots.pop("photo", None)
            continue

        target_path = assets_dir / f"beat_{idx+1:02d}_{sanitize_filename(slide_id)}.png"
        downloaded = False
        if allow_web_search and q:
            downloaded = download_real_web_image(q, target_path)
        if not downloaded:
            generate_cinematic_visual(prompt=prompt, output_path=target_path)

        if target_path.is_file() and target_path.stat().st_size > 0:
            im_hash = hashlib.sha256(target_path.read_bytes()).hexdigest()
            if im_hash in seen_image_hashes:
                # Duplicate image hash! Remove and fall back to large text layout
                target_path.unlink(missing_ok=True)
                slots.pop("image_url", None)
                slots.pop("photo", None)
            else:
                seen_image_hashes.add(im_hash)
                slots["image_url"] = str(target_path)
                if hasattr(slide, "image_prompt"):
                    slide.image_prompt = prompt
                resolved_paths.append(str(target_path))
        else:
            slots.pop("image_url", None)
            slots.pop("photo", None)
            if "photo" in slots:
                slots["photo"] = None

    return resolved_paths
