"""CLI tool to render any Motion Recipe to MP4 and export contact sheets.

Usage:
    python tools/render_recipe.py --recipe glass_fill --params '{"fill_percentage": 75}' --out output/recipe_gallery/glass_fill.mp4
    python tools/render_recipe.py --all --out-dir output/recipe_gallery --contact-sheet output/recipe_gallery/contact_sheet.png
"""
from __future__ import annotations

import argparse
import io
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryFile

# Add repo root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw, ImageFont
from imageio_ffmpeg import get_ffmpeg_exe

from config.settings import ROOT_DIR
from editor.captions import find_font
from pipeline.render_motion import browser_page, capture
from tools.recipe_gallery import VOCAB_RECIPES

DEFAULT_OUT_DIR = ROOT_DIR / "output" / "recipe_gallery"


def get_default_recipe_spec(recipe_name: str) -> dict:
    """Find default specification and test parameters for a given recipe."""
    for r in VOCAB_RECIPES:
        if r["name"] == recipe_name:
            return r
    # Fallback generic spec if not found in VOCAB_RECIPES
    return {
        "name": recipe_name,
        "title": recipe_name.replace("_", " ").title(),
        "scene_type": recipe_name,
        "data": {
            "value": 85,
            "unit": "%",
            "label": recipe_name.replace("_", " ").title(),
            "text": "Minh họa công thức chuyển động",
            "_is_fixture": True,
        },
    }


def render_single_recipe(
    recipe_name: str,
    params: dict | None = None,
    output_path: Path | None = None,
    *,
    duration: float = 4.0,
    scale: float = 0.5,
    fps: int = 24,
    extract_frame_times: list[float] | None = None,
) -> tuple[bool, str, list[bytes]]:
    """Render a single recipe to MP4 and return (success, message, extracted_frame_bytes)."""
    base_spec = get_default_recipe_spec(recipe_name)
    merged_data = dict(base_spec.get("data", {}))
    merged_data["_is_fixture"] = True
    if params:
        merged_data.update(params)

    # Resolution calculation based on 1080x1920 base
    w = int(1080 * scale)
    h = int(1920 * scale)
    size = (w, h)
    font = find_font(ROOT_DIR)

    payload = {
        "width": size[0],
        "height": size[1],
        "duration": duration,
        "words": [],
        "captions": {"enabled": False},
        "depth_3d": False,
        "shots": [
            {
                "start": 0,
                "duration": duration,
                "template": "text_focus",
                "data": merged_data,
                "beats": [],
            }
        ],
        "theme": {"name": "neon_dark"},
        "visual_plan": {
            "scene_type": recipe_name,
            "depth_3d": False,
            "data": merged_data,
            "beats": [
                {"at_sec": 0.5, "action": f"enter_{recipe_name}"},
                {"at_sec": 1.8, "action": f"action_{recipe_name}_step"},
                {"at_sec": 3.2, "action": f"impact_{recipe_name}_glow"},
            ],
            "camera": {"move": "push_in", "amount": 0.04},
            "annotations": [],
        },
    }

    count = int(math.ceil(duration * fps))
    extracted_frames: list[bytes] = []
    target_times = sorted(extract_frame_times or [])

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with browser_page(size) as page, TemporaryFile() as errors:
            capture(page, payload, font)

            # Check if MotionVocabulary has the recipe
            has_func = page.evaluate(
                f"() => Boolean(window.MotionVocabulary && typeof window.MotionVocabulary['{recipe_name}'] === 'function')"
            )
            if not has_func:
                return False, f"MotionVocabulary['{recipe_name}'] không tồn tại trên window", []

            proc = None
            if output_path:
                cmd = [
                    get_ffmpeg_exe(),
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-f",
                    "image2pipe",
                    "-vcodec",
                    "mjpeg",
                    "-framerate",
                    str(fps),
                    "-i",
                    "pipe:0",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "22",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    str(output_path),
                ]
                proc = subprocess.Popen(
                    cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errors
                )

            current_target_idx = 0
            for i in range(count):
                t = min(i / fps, duration - 1e-4)
                page.evaluate(f"t => window.renderAt({t})")
                frame_bytes = page.screenshot(
                    type="jpeg", quality=90, animations="disabled", caret="hide"
                )

                if proc and proc.stdin:
                    proc.stdin.write(frame_bytes)

                if target_times and current_target_idx < len(target_times):
                    target_t = target_times[current_target_idx]
                    # If this frame is the closest to target_t
                    if t >= target_t or i == count - 1:
                        extracted_frames.append(frame_bytes)
                        current_target_idx += 1

            if proc and proc.stdin:
                proc.stdin.close()
                proc.wait()

        return True, "OK", extracted_frames

    except Exception as exc:
        return False, str(exc), []


def build_contact_sheet(
    recipe_frame_map: dict[str, list[bytes]],
    output_png: Path,
    frame_times: list[float],
) -> None:
    """
    Build a contact sheet where:
    - Each row represents 1 recipe (28 rows)
    - Each row has 6 columns corresponding to the 6 frame timestamps
    - Each cell shows the rendered frame and the row has the recipe title on the left
    """
    recipes = list(recipe_frame_map.keys())
    if not recipes:
        return

    thumb_w, thumb_h = 160, 284  # scale down from 540x960
    label_w = 220
    cols = len(frame_times)
    rows = len(recipes)
    header_h = 50

    total_w = label_w + cols * (thumb_w + 10) + 20
    total_h = header_h + rows * (thumb_h + 12) + 20

    sheet = Image.new("RGB", (total_w, total_h), color="#080c14")
    draw = ImageDraw.Draw(sheet)

    try:
        font_header = ImageFont.truetype("arial.ttf", 16)
        font_row = ImageFont.truetype("arial.ttf", 14)
        font_time = ImageFont.truetype("arial.ttf", 12)
    except Exception:
        font_header = ImageFont.load_default()
        font_row = font_header
        font_time = font_header

    # Draw Column Headers (Time Stamps)
    for c_idx, t_val in enumerate(frame_times):
        cx = label_w + 10 + c_idx * (thumb_w + 10)
        draw.text(
            (cx + thumb_w // 2, 18),
            f"t = {t_val:.1f}s",
            fill="#38bdf8",
            font=font_header,
            anchor="mm",
        )

    # Draw Each Row
    for r_idx, r_name in enumerate(recipes):
        ry = header_h + r_idx * (thumb_h + 12)
        # Background stripe for row
        stripe_color = "#0e1626" if r_idx % 2 == 0 else "#090d16"
        draw.rectangle([0, ry, total_w, ry + thumb_h + 10], fill=stripe_color)

        # Label on left
        draw.text(
            (16, ry + thumb_h // 2 - 10),
            f"{r_idx+1}. {r_name}",
            fill="#f8fafc",
            font=font_row,
        )
        fam_text = f"[{VOCAB_RECIPES[r_idx]['title'].split('(')[0].strip() if r_idx < len(VOCAB_RECIPES) else ''}]"
        draw.text(
            (16, ry + thumb_h // 2 + 12),
            fam_text[:24],
            fill="#94a3b8",
            font=font_time,
        )

        frames = recipe_frame_map.get(r_name, [])
        for c_idx, f_bytes in enumerate(frames):
            if c_idx >= cols:
                break
            cx = label_w + 10 + c_idx * (thumb_w + 10)
            try:
                frame_img = Image.open(io.BytesIO(f_bytes)).resize(
                    (thumb_w, thumb_h), Image.Resampling.LANCZOS
                )
                sheet.paste(frame_img, (cx, ry + 5))
                # Border around thumbnail
                draw.rectangle(
                    [cx, ry + 5, cx + thumb_w, ry + 5 + thumb_h],
                    outline="#1e293b",
                    width=1,
                )
            except Exception:
                draw.rectangle(
                    [cx, ry + 5, cx + thumb_w, ry + 5 + thumb_h],
                    fill="#334155",
                    outline="#ef4444",
                    width=2,
                )
                draw.text(
                    (cx + thumb_w // 2, ry + thumb_h // 2),
                    "ERROR",
                    fill="#ef4444",
                    font=font_row,
                    anchor="mm",
                )

    output_png.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_png, format="PNG", quality=95)
    print(f"[OK] Đã xuất contact sheet: {output_png} ({total_w}x{total_h}px)")


def main():
    parser = argparse.ArgumentParser(description="Render Motion Recipes to MP4 and Contact Sheet")
    parser.add_argument("--recipe", type=str, default="", help="Name of recipe to render")
    parser.add_argument("--params", type=str, default="", help="JSON string of recipe parameters")
    parser.add_argument("--out", type=str, default="", help="Output MP4 file path")
    parser.add_argument("--out-dir", type=str, default=str(DEFAULT_OUT_DIR), help="Output directory")
    parser.add_argument("--all", action="store_true", help="Render all 28 recipes in vocabulary")
    parser.add_argument("--duration", type=float, default=4.0, help="Duration in seconds (default: 4.0)")
    parser.add_argument("--scale", type=float, default=0.5, help="Render scale relative to 1080x1920 (default: 0.5)")
    parser.add_argument("--fps", type=int, default=24, help="Frames per second (default: 24)")
    parser.add_argument("--contact-sheet", type=str, default="", help="Path to export contact sheet PNG")

    args = parser.parse_args()

    frame_times = [0.5, 1.2, 2.0, 2.8, 3.5, 4.0]
    out_dir = Path(args.out_dir)

    if args.all:
        print(f"=== BẮT ĐẦU RENDER TẤT CẢ {len(VOCAB_RECIPES)} RECIPES (Scale={args.scale}, {args.duration}s, {args.fps}fps) ===")
        recipe_frame_map: dict[str, list[bytes]] = {}
        error_list = []
        blank_list = []
        identical_list = []

        for idx, r in enumerate(VOCAB_RECIPES, 1):
            r_name = r["name"]
            out_mp4 = out_dir / f"{r_name}.mp4"
            print(f"[{idx:02d}/{len(VOCAB_RECIPES):02d}] Đang render '{r_name}' -> {out_mp4.name}...", end=" ", flush=True)

            t0 = time.time()
            success, msg, frames = render_single_recipe(
                recipe_name=r_name,
                output_path=out_mp4,
                duration=args.duration,
                scale=args.scale,
                fps=args.fps,
                extract_frame_times=frame_times,
            )
            elapsed = time.time() - t0

            if success:
                print(f"[OK] ({elapsed:.1f}s)")
                recipe_frame_map[r_name] = frames
                # Check for blank / identical frames
                if frames:
                    # Quick check if first and last frames are identical (animation frozen)
                    if len(frames) >= 2 and frames[0] == frames[-1]:
                        identical_list.append(r_name)
            else:
                print(f"[LỖI: {msg}]")
                error_list.append((r_name, msg))

        # Build contact sheet
        contact_sheet_path = Path(args.contact_sheet) if args.contact_sheet else (out_dir / "contact_sheet.png")
        print("\n=== ĐANG XUẤT CONTACT SHEET (MỖI HÀNG 1 RECIPE, 6 KHUNG) ===")
        build_contact_sheet(recipe_frame_map, contact_sheet_path, frame_times)

        # Audit Summary
        print("\n=== BÁO CÁO KIỂM THỬ THƯ VIỆN 28 RECIPES ===")
        print(f"- Tổng số recipes kiểm tra: {len(VOCAB_RECIPES)}")
        print(f"- Render thành công: {len(recipe_frame_map)}/{len(VOCAB_RECIPES)}")
        print(f"- Render lỗi: {len(error_list)} {error_list if error_list else '(Không có)'}")
        print(f"- Render trống / hỏng: {len(blank_list)} {blank_list if blank_list else '(Không có)'}")
        print(f"- Render đứng yên / không đổi khung: {len(identical_list)} {identical_list if identical_list else '(Không có)'}")
        return

    # Single recipe mode
    target_recipe = args.recipe or "glass_fill"
    params = json.loads(args.params) if args.params else None
    out_file = Path(args.out) if args.out else (out_dir / f"{target_recipe}.mp4")

    print(f"=== ĐANG RENDER RECIPE: {target_recipe} -> {out_file} ===")
    success, msg, frames = render_single_recipe(
        recipe_name=target_recipe,
        params=params,
        output_path=out_file,
        duration=args.duration,
        scale=args.scale,
        fps=args.fps,
        extract_frame_times=frame_times,
    )
    if success:
        print(f"[THÀNH CÔNG] File MP4: {out_file} ({out_file.stat().st_size} bytes)")
    else:
        print(f"[THẤT BẠI] Lỗi: {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
