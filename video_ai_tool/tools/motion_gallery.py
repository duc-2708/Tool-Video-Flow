"""Motion Gallery: Standalone tool to render 4b Motion Design System recipes to MP4 & contact sheet."""
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

GALLERY_DIR = ROOT_DIR / "output/motion_gallery"
THUMBS_DIR = GALLERY_DIR / "thumbs"

RECIPES = [
    {
        "name": "stat_number_odometer",
        "title": "Stat Number (Odometer Bounce)",
        "scene_type": "stat_number",
        "variant_index": 0,
        "data": {
            "value": 85,
            "unit": "%",
            "label": "Tỷ lệ tăng trưởng vượt trội",
            "text": "Hiệu suất hệ thống"
        },
        "annotations": []
    },
    {
        "name": "stat_number_strike_replace",
        "title": "Stat Number (Strike Replace Pop)",
        "scene_type": "stat_number",
        "variant_index": 1,
        "data": {
            "value": 90,
            "unit": "%",
            "label": "Số liệu sau kiểm định lại",
            "text": "Điều chỉnh dự báo",
            "bars": [{"label": "Cũ", "value": 45}, {"label": "Mới", "value": 90}]
        },
        "annotations": []
    },
    {
        "name": "stat_number_glow_ring",
        "title": "Stat Number (Glow Ring Arc)",
        "scene_type": "stat_number",
        "variant_index": 2,
        "data": {
            "value": 78,
            "unit": "%",
            "label": "Khối lượng công việc hoàn thành",
            "text": "Tiến độ dự án"
        },
        "annotations": []
    },
    {
        "name": "bar_compare_crown",
        "title": "Bar Compare (Stagger Crown)",
        "scene_type": "bar_compare",
        "variant_index": 0,
        "data": {
            "bars": [
                {"label": "Giải pháp A", "value": 45, "unit": "%"},
                {"label": "Giải pháp B", "value": 88, "unit": "%"},
                {"label": "Giải pháp C", "value": 62, "unit": "%"}
            ]
        },
        "annotations": []
    },
    {
        "name": "bar_compare_horizontal",
        "title": "Bar Compare (Horizontal Slide)",
        "scene_type": "bar_compare",
        "variant_index": 1,
        "data": {
            "bars": [
                {"label": "Tốc độ xử lý", "value": 92, "unit": "MB/s"},
                {"label": "Mức tiêu thụ điện", "value": 35, "unit": "W"}
            ]
        },
        "annotations": []
    },
    {
        "name": "flow_chain_packets",
        "title": "Flow Chain (Kinetic Relay)",
        "scene_type": "flow_chain",
        "variant_index": 0,
        "data": {
            "items": [
                "Thu thập dữ liệu",
                "Phân tích chuyên sâu",
                "Kiểm định độc lập",
                "Báo cáo kết quả"
            ]
        },
        "annotations": []
    },
    {
        "name": "hub_spoke_orbit",
        "title": "Hub Spoke (Radial Pulse)",
        "scene_type": "hub_spoke",
        "variant_index": 0,
        "data": {
            "label": "LÕI AI",
            "items": ["Thị giác máy", "Xử lý ngôn ngữ", "Học tăng cường", "Suy luận logic"]
        },
        "annotations": []
    },
    {
        "name": "container_fill_bubbles",
        "title": "Container Fill (Wave & Bubbles)",
        "scene_type": "container_fill",
        "variant_index": 0,
        "data": {
            "value": 72,
            "label": "Dung tích bộ nhớ khả dụng",
            "text": "Ngưỡng chịu tải"
        },
        "annotations": []
    },
    {
        "name": "checklist_sparks",
        "title": "Checklist (Slide & Sparks)",
        "scene_type": "checklist",
        "variant_index": 0,
        "data": {
            "items": [
                "Bảo mật đa tầng xác thực",
                "Hiệu năng phản hồi dưới 10ms",
                "Chuẩn hóa dữ liệu đầu vào"
            ]
        },
        "annotations": []
    },
    {
        "name": "mock_ui_window",
        "title": "Mock UI Window (Fixed Rows)",
        "scene_type": "mock_ui_window",
        "data": {
            "title": "Bảng điều khiển hệ thống",
            "items": [
                "Máy chủ kiểm định Hòa Lạc",
                "Đo lường thời gian trễ",
                "Kiểm tra tính toàn vẹn",
                "Phê duyệt vận hành"
            ]
        },
        "annotations": []
    },
    {
        "name": "magnifier_check",
        "title": "Magnifier Check (Intentional Glide)",
        "scene_type": "magnifier_check",
        "data": {
            "items": [
                "Báo cáo tự công bố",
                "Dữ liệu thử nghiệm thực tế",
                "Chứng nhận từ bên thứ ba"
            ]
        },
        "annotations": []
    },
    {
        "name": "annotation_strike",
        "title": "Annotation (Red Laser Strike)",
        "scene_type": "stat_number",
        "variant_index": 0,
        "data": {
            "value": 50,
            "unit": "%",
            "label": "Số liệu ban đầu",
            "text": "Tuyên bố cũ"
        },
        "annotations": [
            {"type": "strike", "at_sec": 1.0, "text": "Hủy bỏ"}
        ]
    },
    {
        "name": "annotation_stamp",
        "title": "Annotation (Slamming Rubber Stamp)",
        "scene_type": "stat_number",
        "variant_index": 0,
        "data": {
            "value": 99,
            "unit": "%",
            "label": "Thông số phòng lab",
            "text": "Độ chính xác"
        },
        "annotations": [
            {"type": "stamp", "at_sec": 1.2, "text": "ƯỚC LƯỢNG"}
        ]
    },
    {
        "name": "annotation_underline",
        "title": "Annotation (Neon Brush Underline)",
        "scene_type": "stat_number",
        "variant_index": 0,
        "data": {
            "value": 100,
            "unit": "Gbps",
            "label": "Băng thông kết nối",
            "text": "Hạ tầng lõi"
        },
        "annotations": [
            {"type": "underline", "at_sec": 0.8}
        ]
    },
    {
        "name": "versus_split_slam",
        "title": "Versus Split (Slamming VS Clash)",
        "scene_type": "versus_split",
        "variant_index": 0,
        "data": {
            "bars": [
                {"label": "Giải pháp Cũ", "value": 35, "unit": "%"},
                {"label": "Kiến trúc Mới", "value": 92, "unit": "%"}
            ]
        },
        "annotations": []
    },
    {
        "name": "line_chart_draw_bezier",
        "title": "Line Chart Draw (Smooth Curve)",
        "scene_type": "line_chart_draw",
        "variant_index": 0,
        "data": {
            "bars": [
                {"label": "Q1", "value": 25},
                {"label": "Q2", "value": 45},
                {"label": "Q3", "value": 60},
                {"label": "Q4", "value": 95}
            ]
        },
        "annotations": []
    },
    {
        "name": "terminal_typing_code",
        "title": "Terminal Typing (Syntax Highlighting)",
        "scene_type": "terminal_typing",
        "variant_index": 0,
        "data": {
            "title": "deploy — production — aws",
            "items": [
                "git clone https://repo.git",
                "Building vector containers...",
                "Deployment verified successfully!"
            ]
        },
        "annotations": []
    },
    {
        "name": "timeline_sprout",
        "title": "Timeline (Horizontal Nodes Sprout)",
        "scene_type": "timeline",
        "variant_index": 0,
        "data": {
            "items": [
                "2020: Nghiên cứu",
                "2023: Thử nghiệm",
                "2025: Thương mại hóa"
            ]
        },
        "annotations": []
    },
    {
        "name": "funnel_filter_tiers",
        "title": "Funnel (Multi-Stage Filter)",
        "scene_type": "funnel",
        "variant_index": 0,
        "data": {
            "items": [
                "10.000 Yêu cầu",
                "1.500 Phân loại",
                "200 Kiểm định",
                "15 Tối ưu"
            ]
        },
        "annotations": []
    },
    {
        "name": "progress_tracker_segments",
        "title": "Progress Tracker (Segmented Glow)",
        "scene_type": "progress_tracker",
        "variant_index": 0,
        "data": {
            "items": [
                "Bước 1: Nạp",
                "Bước 2: Xử lý",
                "Bước 3: Duyệt",
                "Bước 4: Xuất"
            ]
        },
        "annotations": []
    },
    {
        "name": "source_badge_verified",
        "title": "Source Badge (Verified Shield)",
        "scene_type": "source_badge",
        "variant_index": 0,
        "data": {
            "source": "Viện Nghiên cứu Công nghệ 2025",
            "text": "Xác thực độc lập"
        },
        "annotations": []
    },
    {
        "name": "icon_tile_stagger",
        "title": "Icon Tile (Stagger Glass Grid)",
        "scene_type": "icon_tile",
        "variant_index": 0,
        "data": {
            "items": [
                "Bảo mật lõi",
                "Tốc độ cao",
                "Khả năng mở rộng",
                "Tiết kiệm chi phí"
            ]
        },
        "annotations": []
    },
    {
        "name": "chat_bubble_dialogue",
        "title": "Chat Bubble (Alternating Flow)",
        "scene_type": "chat_bubble_poll",
        "variant_index": 0,
        "data": {
            "items": [
                "Hệ thống đạt chuẩn an toàn không?",
                "Đã kiểm nghiệm đạt 99.8%!",
                "Có sẵn sàng mở rộng quy mô?"
            ]
        },
        "annotations": []
    },
    {
        "name": "gauge_ring_sweep",
        "title": "Gauge Ring (270 Arc Sweep)",
        "scene_type": "gauge_ring",
        "variant_index": 0,
        "data": {
            "value": 82,
            "unit": "%",
            "label": "Tỷ lệ chuẩn hóa",
            "text": "Chỉ số độ tin cậy"
        },
        "annotations": []
    },
    {
        "name": "annotation_all_types",
        "title": "Annotation (Question, Arrow, Cross, Tag)",
        "scene_type": "stat_number",
        "variant_index": 0,
        "data": {
            "value": 65,
            "unit": "%",
            "label": "Tỷ lệ lỗi giảm sâu",
            "text": "Kiểm nghiệm"
        },
        "annotations": [
            {"type": "question", "at_sec": 0.5},
            {"type": "tag", "at_sec": 0.8, "text": "HOT"},
            {"type": "arrow", "at_sec": 1.2},
            {"type": "check", "at_sec": 1.6}
        ]
    }
]


def render_recipe_video(recipe, output_path, thumb_path, *, size=(540, 960), fps=24, duration=3.5, font=None):
    """Render a single recipe to MP4 and save a middle snapshot."""
    font = font or find_font(ROOT_DIR)

    payload = {
        "width": size[0],
        "height": size[1],
        "duration": duration,
        "words": [],
        "captions": {"enabled": False},
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
            "variant_index": recipe.get("variant_index", 0),
            "data": recipe["data"],
            "beats": [
                {"at_sec": 1.2, "action": "beat_hit"}
            ],
            "camera": {"move": "push_in", "amount": 0.05},
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


def create_contact_sheet(thumb_paths, output_path, cols=4):
    """Combine rendered thumbnails into a grid contact sheet."""
    images = []
    for tp in thumb_paths:
        if tp.is_file():
            img = Image.open(tp)
            # Resize for compact sheet: 270x480
            images.append((tp.stem, img.resize((270, 480), Image.Resampling.LANCZOS)))

    if not images:
        return

    n = len(images)
    rows = math.ceil(n / cols)
    cell_w, cell_h = 270, 520
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), color="#080c17")
    draw = ImageDraw.Draw(sheet)

    for idx, (title, img) in enumerate(images):
        col = idx % cols
        row = idx // cols
        x = col * cell_w
        y = row * cell_h

        # Paste thumb
        sheet.paste(img, (x, y))

        # Draw label bar
        draw.rectangle([x, y + 480, x + cell_w, y + cell_h], fill="#111c2e")
        clean_title = title.replace("_", " ")
        draw.text((x + 10, y + 490), clean_title[:24], fill="#38bdf8")

    sheet.save(output_path, "PNG")


def main():
    parser = argparse.ArgumentParser(description="Render Motion Design System Gallery clips.")
    parser.add_argument("--recipe", choices=[r["name"] for r in RECIPES], help="Render specific recipe")
    parser.add_argument("--scale", type=float, default=0.5, choices=[0.5, 1.0])
    parser.add_argument("--fps", type=int, default=24, choices=[24, 30])
    args = parser.parse_args()

    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)

    targets = [r for r in RECIPES if not args.recipe or r["name"] == args.recipe]
    full_w, full_h = (1080, 1920)
    size = (round(full_w * args.scale), round(full_h * args.scale))
    font = find_font(ROOT_DIR)

    print(f"=== RENDERING MOTION GALLERY ({len(targets)} items, scale={args.scale}, fps={args.fps}) ===")
    start_total = time.perf_counter()
    thumb_paths = []

    for idx, rec in enumerate(targets, 1):
        name = rec["name"]
        mp4_path = GALLERY_DIR / f"{name}.mp4"
        thumb_path = THUMBS_DIR / f"{name}.jpg"
        print(f"[{idx}/{len(targets)}] Rendering {name} ({rec['title']})...", end="", flush=True)

        t0 = time.perf_counter()
        render_recipe_video(rec, mp4_path, thumb_path, size=size, fps=args.fps, duration=3.5, font=font)
        dt = time.perf_counter() - t0
        print(f" done in {dt:.2f}s -> {mp4_path.name}")
        thumb_paths.append(thumb_path)

    # Generate Contact Sheet
    contact_sheet_path = GALLERY_DIR / "contact_sheet.png"
    print(f"Building contact sheet -> {contact_sheet_path}...")
    create_contact_sheet(thumb_paths, contact_sheet_path, cols=4)

    total_time = time.perf_counter() - start_total
    print(f"=== ALL GALLERY ITEMS RENDERED in {total_time:.2f}s ===")
    print(f"Clips directory: {GALLERY_DIR}")
    print(f"Contact sheet: {contact_sheet_path}")


if __name__ == "__main__":
    main()
