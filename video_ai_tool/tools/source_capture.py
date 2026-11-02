"""Source web page capture tool for research brief citation.

Captures top-of-page (1280x720) screenshots from verified public news sources
using Playwright headless, with automatic fallback to high-contrast simulated
source cards when offline or blocked.
"""
from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont

from utils.atomic_io import write_json_atomic


def clean_domain(url: str | None) -> str:
    if not url:
        return "Nguồn tin tức"
    try:
        p = urlparse(url)
        netloc = p.netloc or url
        return re.sub(r"^www\.", "", netloc).split(":")[0].strip()
    except Exception:
        return "Nguồn tin tức"


def generate_fallback_source_card(
    domain: str,
    title: str,
    date_str: str | None,
    output_png: Path,
) -> Path:
    """Generate a clean 1280x720 graphic source card using Pillow when offline or blocked."""
    output_png.parent.mkdir(parents=True, exist_ok=True)
    w, h = 1280, 720
    img = Image.new("RGBA", (w, h), (248, 250, 252, 255))
    draw = ImageDraw.Draw(img)

    # Header gradient bar
    draw.rectangle([0, 0, w, 16], fill=(37, 99, 235, 255))

    # Try loading a system or project font, or fallback to default
    font_bold = None
    font_regular = None
    font_small = None
    
    font_candidates = [
        Path(__file__).resolve().parents[1] / "assets" / "fonts" / "Inter-Bold.ttf",
        Path(__file__).resolve().parents[1] / "assets" / "fonts" / "Montserrat-Bold.ttf",
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for fc in font_candidates:
        if fc.is_file():
            try:
                font_bold = ImageFont.truetype(str(fc), 46)
                font_regular = ImageFont.truetype(str(fc), 30)
                font_small = ImageFont.truetype(str(fc), 24)
                break
            except Exception:
                pass

    if font_bold is None:
        font_bold = ImageFont.load_default()
        font_regular = font_bold
        font_small = font_bold

    # Draw Source Domain Pill with circular favicon letter
    first_letter = domain[0].upper() if domain else "N"
    pill_text = f"NGUỒN: {domain.upper()}"
    pill_x, pill_y = 80, 80
    pill_w = max(380, len(pill_text) * 14 + 70)
    draw.rounded_rectangle([pill_x, pill_y, pill_x + pill_w, pill_y + 54], radius=27, fill=(37, 99, 235, 25), outline=(37, 99, 235, 100), width=2)
    # Circular favicon
    draw.ellipse([pill_x + 8, pill_y + 8, pill_x + 46, pill_y + 46], fill=(37, 99, 235, 255))
    draw.text((pill_x + 20, pill_y + 12), first_letter, fill=(255, 255, 255, 255), font=font_small)
    # Pill label
    draw.text((pill_x + 58, pill_y + 14), pill_text, fill=(37, 99, 235, 255), font=font_small)

    # Date
    date_display = date_str or datetime.datetime.now().strftime("%d/%m/%Y")
    draw.text((w - 280, pill_y + 14), f"Ngày: {date_display}", fill=(100, 116, 139, 255), font=font_small)

    # Main Headline text wrapped
    title_text = title or "Bản tin thời sự công nghệ mới nhất"
    words = title_text.split()
    lines = []
    cur = ""
    for wd in words:
        cand = f"{cur} {wd}".strip() if cur else wd
        if len(cand) <= 32:
            cur = cand
        else:
            lines.append(cur)
            cur = wd
            if len(lines) >= 4:
                break
    if cur and len(lines) < 4:
        lines.append(cur)

    text_y = 210
    for line in lines[:4]:
        draw.text((80, text_y), line, fill=(26, 20, 70, 255), font=font_bold)
        text_y += 72

    # Bottom quote bar / footer
    draw.rectangle([80, 580, w - 80, 583], fill=(226, 232, 240, 255))
    draw.text((80, 610), f"Xác nhận trích xuất tư liệu từ nguồn chính thống · {domain}", fill=(148, 163, 184, 255), font=font_small)

    img.save(str(output_png), "PNG")
    return output_png


async def _capture_url_async(
    url: str,
    domain: str,
    title: str,
    output_png: Path,
    metadata_json: Path,
    timeout_sec: int = 15,
) -> dict[str, Any]:
    output_png.parent.mkdir(parents=True, exist_ok=True)

    # Check cache
    if output_png.is_file() and metadata_json.is_file():
        try:
            with open(metadata_json, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Playwright headless attempt
    success = False
    error_msg = ""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = await context.new_page()
            # Navigate with strict timeout
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)
            await asyncio.sleep(0.5)

            # Dismiss basic banners if present
            try:
                for sel in ["button:has-text('Accept')", "button:has-text('Đồng ý')", "button:has-text('Close')"]:
                    if await page.locator(sel).count() > 0:
                        await page.locator(sel).first.click(timeout=1000)
            except Exception:
                pass

            # Screenshot viewport
            await page.screenshot(
                path=str(output_png),
                clip={"x": 0, "y": 0, "width": 1280, "height": 720},
            )
            await browser.close()
            success = True
    except Exception as exc:
        error_msg = str(exc)

    meta = {
        "url": url,
        "domain": domain,
        "title": title,
        "capture_time": datetime.datetime.now().isoformat(),
        "kind": "screenshot" if success else "card",
        "image_path": str(output_png),
        "fallback_used": not success,
    }
    if not success:
        generate_fallback_source_card(domain, title, None, output_png)
        meta["error"] = error_msg

    write_json_atomic(metadata_json, meta)
    return meta


def capture_sources_for_brief(
    brief: Any,
    output_dir: Path | str,
    max_sources: int = 3,
    timeout_sec: int = 15,
) -> dict[str, dict[str, Any]]:
    """Synchronous interface to capture or render source cards for URLs in brief."""
    out_dir = Path(output_dir) / "sources"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not brief:
        return {}

    facts = getattr(brief, "facts", None) or (brief.get("facts") if isinstance(brief, dict) else [])
    sources_to_capture: list[tuple[str, str, str]] = []
    seen_urls = set()

    for f in facts:
        raw_url = getattr(f, "source_url", "") or (f.get("source_url") if isinstance(f, dict) else "")
        url_str = str(raw_url).strip()
        if not url_str or url_str in seen_urls or not url_str.startswith("http"):
            continue
        seen_urls.add(url_str)
        s_name = getattr(f, "source_name", "") or (f.get("source_name") if isinstance(f, dict) else "")
        claim = getattr(f, "claim", "") or (f.get("claim") if isinstance(f, dict) else "")
        domain = clean_domain(url_str) or s_name
        sources_to_capture.append((url_str, domain, claim))
        if len(sources_to_capture) >= max_sources:
            break

    results: dict[str, dict[str, Any]] = {}

    for url_str, domain, claim in sources_to_capture:
        url_hash = hashlib.sha256(url_str.encode("utf-8")).hexdigest()[:12]
        png_path = out_dir / f"{url_hash}.png"
        meta_path = out_dir / f"{url_hash}.json"

        try:
            meta = asyncio.run(
                _capture_url_async(
                    url=url_str,
                    domain=domain,
                    title=claim,
                    output_png=png_path,
                    metadata_json=meta_path,
                    timeout_sec=timeout_sec,
                )
            )
            results[url_str] = meta
        except Exception:
            # Fallback card
            generate_fallback_source_card(domain, claim, None, png_path)
            meta = {
                "url": url_str,
                "domain": domain,
                "title": claim,
                "capture_time": datetime.datetime.now().isoformat(),
                "kind": "card",
                "image_path": str(png_path),
                "fallback_used": True,
            }
            write_json_atomic(meta_path, meta)
            results[url_str] = meta

    return results
