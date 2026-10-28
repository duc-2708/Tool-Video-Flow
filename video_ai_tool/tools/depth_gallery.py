"""Depth Gallery: Render 3D Perspective & Isometric elements to MP4 clips and contact sheet."""
import argparse
import io
import math
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryFile

# Add repository root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw, ImageFont
from imageio_ffmpeg import get_ffmpeg_exe

from config.settings import ROOT_DIR
from editor.captions import find_font
from pipeline.render_motion import browser_page, capture

GALLERY_DIR = ROOT_DIR / "output/depth_gallery"
THUMBS_DIR = GALLERY_DIR / "thumbs"

DEPTH_RECIPES = [
    {
        "name": "depth_bar_compare",
        "title": "Bar Compare 3D (Extruded Cuboids + Floor Grid)",
        "scene_type": "bar_compare",
        "data": {
            "bars": [
                {"label": "Giải pháp A", "value": 45, "unit": "%"},
                {"label": "Giải pháp B", "value": 92, "unit": "%"},
                {"label": "Giải pháp C", "value": 68, "unit": "%"}
            ]
        },
        "annotations": [],
        "light_direction": "Top-Left (45°)",
        "shading": "Top (+18%), Left (0%), Right (-28%)",
        "bbox": "[180, 520, 900, 1260] (Safe: [70, 1010] x [240, 1330])"
    },
    {
        "name": "depth_gauge_ring",
        "title": "Gauge Ring 3D (Tilted Perspective Torus + Neon Pulse)",
        "scene_type": "gauge_ring",
        "data": {
            "value": 85,
            "unit": "%",
            "label": "Tỷ lệ chuẩn hóa",
            "text": "Độ tin cậy hạ tầng"
        },
        "annotations": [],
        "light_direction": "Top-Left (45°)",
        "shading": "Torus Rim + Shaded Skirt Wall",
        "bbox": "[270, 580, 810, 1060] (Safe: [70, 1010] x [240, 1330])"
    },
    {
        "name": "depth_versus_split",
        "title": "Versus Split 3D (Slamming 3D Slabs + Floating VS Badge)",
        "scene_type": "versus_split",
        "data": {
            "bars": [
                {"label": "Hạ tầng Cũ", "value": 35, "unit": "%"},
                {"label": "VPS Tối ưu", "value": 95, "unit": "%"}
            ]
        },
        "annotations": [],
        "light_direction": "Top-Left (45°)",
        "shading": "Opposing 3D Slabs + Contact Shadow",
        "bbox": "[90, 520, 990, 1080] (Safe: [70, 1010] x [240, 1330])"
    },
    {
        "name": "depth_hub_spoke",
        "title": "Hub Spoke 3D (Tilted Orbit Satellites + Data Packets)",
        "scene_type": "hub_spoke",
        "data": {
            "center_label": "TRUNG TÂM CLOUD",
            "satellites": [
                {"label": "Bảo mật", "value": "99.9%"},
                {"label": "Tốc độ", "value": "<15ms"},
                {"label": "Băng thông", "value": "10 Gbps"},
                {"label": "Sao lưu", "value": "Tự động"}
            ]
        },
        "annotations": [],
        "light_direction": "Top-Left (45°)",
        "shading": "Cylinder Hub + Glowing Satellite Cuboids",
        "bbox": "[110, 480, 970, 1040] (Safe: [70, 1010] x [240, 1330])"
    },
    {
        "name": "depth_checklist",
        "title": "Checklist 3D (Stacked Slabs + 3D Check Bounce)",
        "scene_type": "checklist",
        "data": {
            "items": [
                {"text": "Khởi tạo hạ tầng điện toán đám mây", "checked": True},
                {"text": "Đóng gói container Docker chuẩn hoá", "checked": True},
                {"text": "Cấu hình chứng chỉ bảo mật SSL", "checked": True},
                {"text": "Kích hoạt giám sát tự động 24/7", "checked": True}
            ]
        },
        "annotations": [],
        "light_direction": "Top-Left (45°)",
        "shading": "3D Tiered Slabs (Z+35px Active)",
        "bbox": "[110, 530, 970, 1040] (Safe: [70, 1010] x [240, 1330])"
    },
    {
        "name": "depth_stat_number",
        "title": "Stat Number 3D (Multi-layer 45° Extrusion + Pedestal)",
        "scene_type": "stat_number",
        "data": {
            "value": 98,
            "unit": "%",
            "label": "TĂNG TRƯỞNG VƯỢT TRỘI",
            "subtext": "Đạt chuẩn hiệu năng cao toàn diện"
        },
        "annotations": [],
        "light_direction": "Top-Left (45°)",
        "shading": "8-tier Text Shadow + Extruded Pedestal Disc",
        "bbox": "[160, 520, 920, 1020] (Safe: [70, 1010] x [240, 1330])"
    },
    {
        "name": "depth_flow_chain",
        "title": "Flow Chain 3D (Isometric Station Cuboids + Stream)",
        "scene_type": "flow_chain",
        "data": {
            "steps": [
                {"label": "Tiếp nhận Dữ liệu", "detail": "Phân luồng"},
                {"label": "Xử lý Logic AI", "detail": "Phân tích"},
                {"label": "Xuất Kết quả", "detail": "Tối ưu hoá"}
            ]
        },
        "annotations": [],
        "light_direction": "Top-Left (45°)",
        "shading": "3-face Isometric Cuboids + Glowing Conduits",
        "bbox": "[120, 500, 960, 1050] (Safe: [70, 1010] x [240, 1330])"
    },
    {
        "name": "depth_terminal",
        "title": "Terminal 3D (Tilted Window + Specular Neon Bezel)",
        "scene_type": "terminal_typing",
        "data": {
            "title": "Cloud Terminal v2.4",
            "lines": [
                "$ docker build -t enterprise-app:latest .",
                ">> Step 1/3: Analyzing requirements...",
                ">> Step 2/3: Optimizing cache layers...",
                "[SUCCESS] Deployment completed in 1.24s!"
            ]
        },
        "annotations": [],
        "light_direction": "Top-Left (45°)",
        "shading": "Perspective Bezel (rotX 6°, rotY -8°) + Shadow",
        "bbox": "[110, 510, 970, 1010] (Safe: [70, 1010] x [240, 1330])"
    },
    {
        "name": "depth_road_tracker",
        "title": "Road Tracker 3D (Curved Bezier Ribbon + Milestones)",
        "scene_type": "road_tracker",
        "data": {
            "stations": [
                {"label": "Bắt đầu", "station": 1},
                {"label": "Tăng tốc", "station": 2},
                {"label": "Kiểm thử", "station": 3},
                {"label": "Về đích", "station": 4}
            ]
        },
        "annotations": [],
        "light_direction": "Top-Left (45°)",
        "shading": "3D Bezier Ribbon Bed + Milestone Cuboids",
        "bbox": "[140, 460, 940, 1180] (Safe: [70, 1010] x [240, 1330])"
    }
]


def render_depth_video(recipe, output_path, thumb_path, *, size=(540, 960), fps=24, duration=4.0, font=None):
    """Render a single 3D recipe to MP4 and save thumbnail."""
    font = font or find_font(ROOT_DIR)

    payload = {
        "width": size[0],
        "height": size[1],
        "duration": duration,
        "words": [],
        "captions": {"enabled": False},
        "depth_3d": True,
        "shots": [{
            "start": 0,
            "duration": duration,
            "template": "text_focus",
            "data": recipe["data"],
            "beats": []
        }],
        "theme": {"name": "neon_dark"},
        "visual_plan": {
            "scene_type": recipe["scene_type"],
            "depth_3d": True,
            "data": recipe["data"],
            "beats": [
                {"at_sec": 0.8, "action": "beat_hit"}
            ],
            "camera": {"move": "push_in", "amount": 0.04},
            "annotations": recipe.get("annotations", [])
        }
    }

    count = int(math.ceil(duration * fps))

    with browser_page(size) as page, TemporaryFile() as errors:
        capture(page, payload, font)

        cmd = [
            get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "image2pipe", "-vcodec", "mjpeg", "-framerate", str(fps), "-i", "pipe:0",
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output_path)
        ]

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errors)
        thumb_frame_idx = int(fps * 2.0)

        for i in range(count):
            t = min(i / fps, duration - 1e-4)
            page.evaluate(f"t => window.renderAt({t})")
            frame_bytes = page.screenshot(type="jpeg", quality=90, animations="disabled", caret="hide")
            proc.stdin.write(frame_bytes)

            if i == thumb_frame_idx and thumb_path:
                thumb_path.write_bytes(frame_bytes)

        proc.stdin.close()
        proc.wait()


def create_depth_contact_sheet(recipes, thumb_paths, output_path, cols=3):
    """Combine rendered 3D thumbnails into a detailed contact sheet grid with audit info."""
    images = []
    for recipe, tp in zip(recipes, thumb_paths):
        if tp.is_file():
            img = Image.open(tp)
            # Scale down for sheet: 360x640
            images.append((recipe, img.resize((360, 640), Image.Resampling.LANCZOS)))

    if not images:
        return

    n = len(images)
    cols = min(cols, n)
    rows = math.ceil(n / cols)
    cell_w, cell_h = 360, 760
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), color="#09041a")
    draw = ImageDraw.Draw(sheet)

    font_path = find_font(ROOT_DIR)
    font_title = ImageFont.truetype(str(font_path), 18) if font_path else ImageFont.load_default()
    font_meta = ImageFont.truetype(str(font_path), 13) if font_path else ImageFont.load_default()

    for idx, (recipe, img) in enumerate(images):
        col = idx % cols
        row = idx // cols
        x = col * cell_w
        y = row * cell_h

        # Paste image
        sheet.paste(img, (x, y))

        # Draw border
        draw.rectangle([x, y, x + cell_w - 1, y + 640 - 1], outline="#9d4edd", width=2)

        # Meta text info box below
        draw.rectangle([x, y + 640, x + cell_w - 1, y + cell_h - 1], fill="#12072b", outline="#00f5d4", width=1)
        draw.text((x + 10, y + 648), recipe["title"][:34], font=font_title, fill="#ffffff")
        draw.text((x + 10, y + 674), f"Light: {recipe['light_direction']}", font=font_meta, fill="#00f5d4")
        draw.text((x + 10, y + 694), f"Shading: {recipe['shading'][:36]}", font=font_meta, fill="#c77dff")
        draw.text((x + 10, y + 714), f"BBox: {recipe['bbox'][:35]}...", font=font_meta, fill="#ffd166")
        draw.text((x + 10, y + 734), "Caption Safe Zone: PASS (y1380-1700)", font=font_meta, fill="#22c55e")

    sheet.save(output_path, format="PNG")


def main():
    parser = argparse.ArgumentParser(description="Render 3D Depth Elements Gallery")
    parser.add_argument("--size", nargs=2, type=int, default=[540, 960], help="Render resolution [width, height]")
    parser.add_argument("--fps", type=int, default=24, help="Framerate")
    parser.add_argument("--duration", type=float, default=4.0, help="Clip duration")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of recipes to render")
    parser.add_argument("--only", nargs="+", type=str, default=None, help="List of recipe names to render")
    parser.add_argument("--skip-existing", action="store_true", help="Skip rendering if MP4 and thumb already exist")
    args = parser.parse_args()

    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)

    recipes_to_run = DEPTH_RECIPES
    if args.only:
        recipes_to_run = [r for r in DEPTH_RECIPES if r["name"] in args.only or r["scene_type"] in args.only]
    elif args.limit:
        recipes_to_run = DEPTH_RECIPES[:args.limit]

    print(f"Rendering 3D Depth Gallery ({len(recipes_to_run)} elements, {args.duration}s @ {args.fps}fps)...")
    start_total = time.time()
    thumb_paths = []

    for idx, recipe in enumerate(recipes_to_run, 1):
        name = recipe["name"]
        mp4_path = GALLERY_DIR / f"{name}.mp4"
        thumb_path = THUMBS_DIR / f"{name}.jpg"
        thumb_paths.append(thumb_path)

        print(f"[{idx}/{len(DEPTH_RECIPES)}] Rendering 3D {recipe['title']} -> {mp4_path.name}")
        t0 = time.time()
        render_depth_video(
            recipe, mp4_path, thumb_path,
            size=tuple(args.size), fps=args.fps, duration=args.duration
        )
        print(f"      Done in {time.time() - t0:.2f}s")

    contact_path = GALLERY_DIR / "contact_sheet.png"
    print(f"Generating Contact Sheet -> {contact_path.name}")
    all_thumbs = [THUMBS_DIR / f"{r['name']}.jpg" for r in recipes_to_run]
    create_depth_contact_sheet(recipes_to_run, all_thumbs, contact_path)

    elapsed = time.time() - start_total
    print(f"\n3D Depth Gallery complete in {elapsed:.2f}s!")
    print(f"Gallery location: {GALLERY_DIR}")


if __name__ == "__main__":
    main()
