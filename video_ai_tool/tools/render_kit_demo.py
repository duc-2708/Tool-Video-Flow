"""Render Offline Demo Video for Motion Kit v2 (~30-35s).

Uses at least: kit_stat, kit_chart_bar, kit_chart_line, kit_photo (synthetic Pillow image),
kit_list, kit_quote, kit_title. All sample data is explicitly labeled 'mẫu'.
Generates MP4 + Contact Sheet (1 frame / 0.5s) + Quality Audit JSON.
Zero external API calls.
"""
from __future__ import annotations

import base64
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import time

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg
from playwright.sync_api import sync_playwright

from editor.motion.kit import bundle_kit
from tools.audit_style import audit_kit_project

OUTPUT_DIR = ROOT_DIR / "output" / "kit_demo"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_synthetic_photo(out_path: Path) -> str:
    """Generate a clean synthetic tech illustration with Pillow (no real human faces)."""
    w, h = 910, 1000
    im = Image.new("RGB", (w, h), color=(15, 23, 42))
    draw = ImageDraw.Draw(im)

    # Background gradient / grid
    for y in range(0, h, 40):
        draw.line([(0, y), (w, y)], fill=(30, 41, 59), width=1)
    for x in range(0, w, 40):
        draw.line([(x, 0), (x, h)], fill=(30, 41, 59), width=1)

    # Central abstract tech chip
    cx, cy = w // 2, h // 2 - 40
    chip_size = 280
    draw.rectangle([cx - chip_size // 2, cy - chip_size // 2, cx + chip_size // 2, cy + chip_size // 2],
                   fill=(37, 99, 235), outline=(96, 165, 250), width=6)

    # Core glowing die
    core_size = 140
    draw.rectangle([cx - core_size // 2, cy - core_size // 2, cx + core_size // 2, cy + core_size // 2],
                   fill=(124, 58, 237), outline=(167, 139, 250), width=4)

    # Traces radiating outward
    for angle_deg in range(0, 360, 30):
        rad = math.radians(angle_deg)
        x1 = cx + int((chip_size // 2 + 10) * math.cos(rad))
        y1 = cy + int((chip_size // 2 + 10) * math.sin(rad))
        x2 = cx + int((chip_size // 2 + 90) * math.cos(rad))
        y2 = cy + int((chip_size // 2 + 90) * math.sin(rad))
        draw.line([(x1, y1), (x2, y2)], fill=(56, 189, 248), width=4)
        draw.ellipse([x2 - 6, y2 - 6, x2 + 6, y2 + 6], fill=(255, 255, 255))

    im.save(out_path, format="JPEG", quality=95)

    buffer = io.BytesIO()
    im.save(buffer, format="JPEG", quality=95)
    b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def build_demo_data(photo_data_uri: str) -> dict:
    """Build pure grounded demo slide payload for Motion Kit v2."""
    slides = [
        {
            "id": "slide_1",
            "layout": "kit_title",
            "t_start": 0.0,
            "duration": 5.0,
            "t_end": 5.0,
            "narration": "Công nghệ bán dẫn thế hệ mới với kiến trúc xử lý vượt bậc.",
            "slots": {
                "pill": "TIÊU ĐIỂM (MẪU)",
                "title": "CÔNG NGHỆ BÁN DẪN ĐỘT PHÁ MỚI",
                "subtitle": "Kiến trúc vi xử lý thế hệ mới với hiệu năng tính toán tăng tốc vượt bậc.",
            }
        },
        {
            "id": "slide_2",
            "layout": "kit_stat",
            "t_start": 5.0,
            "duration": 5.0,
            "t_end": 10.0,
            "narration": "Quy mô thị trường điện toán đạt mức 128 tỷ USD.",
            "slots": {
                "pill": "SỐ LIỆU (MẪU)",
                "value": 128,
                "unit": "Tỷ USD",
                "label": "Quy mô thị trường điện toán toàn cầu",
                "delta": {"text": "+24%", "direction": "up"}
            }
        },
        {
            "id": "slide_3",
            "layout": "kit_chart_bar",
            "t_start": 10.0,
            "duration": 5.0,
            "t_end": 15.0,
            "narration": "Thị phần vi xử lý di động phân bổ rõ rệt giữa các đơn vị.",
            "slots": {
                "pill": "BIỂU ĐỒ (MẪU)",
                "title": "Thị Phần Vi Xử Lý Di Động",
                "unit": "%",
                "series": [
                    {"label": "Hãng A", "value": 42},
                    {"label": "Hãng B", "value": 28},
                    {"label": "Hãng C", "value": 18},
                    {"label": "Khác", "value": 12}
                ]
            }
        },
        {
            "id": "slide_4",
            "layout": "kit_chart_line",
            "t_start": 15.0,
            "duration": 5.0,
            "t_end": 20.0,
            "narration": "Tốc độ xử lý tăng trưởng liên tục qua các giai đoạn.",
            "slots": {
                "pill": "TIẾN TRÌNH (MẪU)",
                "title": "Tốc Độ Xử Lý Qua Các Năm",
                "unit": "TOPS",
                "series": [
                    {"label": "2022", "value": 30},
                    {"label": "2023", "value": 45},
                    {"label": "2024", "value": 75},
                    {"label": "2025", "value": 120}
                ]
            }
        },
        {
            "id": "slide_5",
            "layout": "kit_photo",
            "t_start": 20.0,
            "duration": 5.0,
            "t_end": 25.0,
            "narration": "Mô hình kiến trúc chip lượng tử thử nghiệm trong phòng lab.",
            "slots": {
                "path": photo_data_uri,
                "name": "Kiến Trúc Lượng Tử Mẫu",
                "role": "Mô hình thử nghiệm phòng thí nghiệm",
                "credit": "Nguồn: Nghiên cứu nội bộ (Mẫu)",
            }
        },
        {
            "id": "slide_6",
            "layout": "kit_list",
            "t_start": 25.0,
            "duration": 5.0,
            "t_end": 30.0,
            "narration": "3 đột phá công nghệ chính mang lại bước tiến nhảy vọt.",
            "slots": {
                "pill": "ĐẶC ĐIỂM (MẪU)",
                "title": "3 Điểm Nhấn Công Nghệ Chính",
                "items": [
                    "Tiết kiệm 40% điện năng tiêu thụ",
                    "Băng thông bộ nhớ mở rộng gấp 3 lần",
                    "Tích hợp sẵn bộ gia tốc AI chuyên dụng"
                ]
            }
        },
        {
            "id": "slide_7",
            "layout": "kit_quote",
            "t_start": 30.0,
            "duration": 5.0,
            "t_end": 35.0,
            "narration": "Chuyên gia nhận định công nghệ sẽ định hình lại toàn bộ ngành.",
            "slots": {
                "pill": "Ý KIẾN (MẪU)",
                "quote": "Công nghệ này sẽ định hình lại toàn bộ ngành công nghiệp bán dẫn trong thập kỷ tới.",
                "author": "Chuyên Gia Phân Tích",
                "role": "Viện Nghiên Cứu Công Nghệ (Mẫu)",
            }
        }
    ]

    return {
        "width": 1080,
        "height": 1920,
        "duration": 35.0,
        "brand_name": "TIN CÔNG NGHỆ",
        "source_domain": "tech-insight.vn",
        "slides": slides,
    }


def render_demo():
    print("=== BẮT ĐẦU KẾT XUẤT VIDEO DEMO MOTION KIT v2 ===")
    t0 = time.time()

    # 1. Generate synthetic photo
    photo_file = OUTPUT_DIR / "sample_tech_chip.jpg"
    photo_uri = generate_synthetic_photo(photo_file)
    print(f"1. Đã sinh ảnh tổng hợp Pillow: {photo_file.name}")

    # 2. Build payload
    payload = build_demo_data(photo_uri)
    payload_json = json.dumps(payload, ensure_ascii=False)
    (OUTPUT_DIR / "slide_script.json").write_text(json.dumps({"slides": payload["slides"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "brief.json").write_text(json.dumps({
        "topic": "Công nghệ bán dẫn",
        "facts": [{"claim": "Quy mô thị trường 128 tỷ USD", "evidence_quote": "128 tỷ USD"}]
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3. Bundle Kit v2 assets
    kit_css, kit_js, digest = bundle_kit()
    print(f"2. Đã bundle Motion Kit v2 (digest: {digest[:12]})")

    html_content = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
{kit_css}
</style>
</head>
<body>
<div id="stage"></div>
<script>
window.MOTION_DATA = {payload_json};
</script>
<script>
{kit_js}
</script>
</body>
</html>"""

    # 4. Render frames via Playwright into FFmpeg
    video_out = OUTPUT_DIR / "kit_demo.mp4"
    fps = 30
    total_duration = payload["duration"]
    total_frames = int(total_duration * fps)

    ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_cmd = [
        ffmpeg_bin,
        "-y",
        "-f", "image2pipe",
        "-vcodec", "mjpeg",
        "-framerate", str(fps),
        "-i", "pipe:0",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(video_out),
    ]

    print(f"3. Bắt đầu render {total_frames} khung hình ({total_duration}s @ {fps}fps) qua Playwright...")
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    extracted_for_contact_sheet: list[tuple[float, Image.Image]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-gpu", "--disable-lcd-text"])
        context = browser.new_context(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
        page = context.new_page()
        page.set_content(html_content, wait_until="load")
        page.evaluate("() => document.fonts.ready")
        page.evaluate("() => window.renderAt(0)")

        # Render frames
        contact_step_sec = 0.5
        next_contact_t = 0.0

        for frame_idx in range(total_frames):
            cur_t = frame_idx / fps
            page.evaluate(f"t => window.renderAt({cur_t:.4f})")
            img_bytes = page.screenshot(type="jpeg", quality=90)
            proc.stdin.write(img_bytes)

            if cur_t >= next_contact_t - 1e-4:
                # Capture frame for contact sheet (scaled to 180x320)
                im = Image.open(io.BytesIO(img_bytes)).resize((180, 320), Image.Resampling.LANCZOS)
                extracted_for_contact_sheet.append((cur_t, im))
                next_contact_t += contact_step_sec

            if frame_idx > 0 and frame_idx % 150 == 0:
                print(f"   -> Đã render {frame_idx}/{total_frames} khung ({cur_t:.1f}s)...")

        proc.stdin.close()
        proc.wait()
        browser.close()

    print(f"4. Video render hoàn tất: {video_out} (kích thước: {video_out.stat().st_size / 1024 / 1024:.2f} MB)")

    # 5. Build Contact Sheet (1 frame every 0.5s)
    print("5. Ghép Contact Sheet 1 khung/0.5s...")
    n_contact = len(extracted_for_contact_sheet)
    cols = 10
    rows = math.ceil(n_contact / cols)
    thumb_w, thumb_h = 180, 320
    header_h = 40
    cell_w = thumb_w + 10
    cell_h = thumb_h + header_h + 10

    sheet_w = cols * cell_w + 20
    sheet_h = rows * cell_h + 40
    sheet_img = Image.new("RGB", (sheet_w, sheet_h), color=(15, 23, 42))
    sheet_draw = ImageDraw.Draw(sheet_img)

    for idx, (t_sec, thumb) in enumerate(extracted_for_contact_sheet):
        col = idx % cols
        row = idx // cols
        x = 20 + col * cell_w
        y = 20 + row * cell_h

        sheet_img.paste(thumb, (x, y + header_h))
        # Label time
        sheet_draw.text((x + 8, y + 10), f"t={t_sec:.1f}s", fill=(241, 245, 249))

    contact_sheet_path = OUTPUT_DIR / "contact_sheet.jpg"
    sheet_img.save(contact_sheet_path, format="JPEG", quality=92)
    print(f"   -> Đã lưu Contact Sheet: {contact_sheet_path} ({n_contact} khung hình)")

    # 6. Quality Audit
    print("6. Chạy bộ kiểm định chất lượng thật (Quality Audit)...")
    audit_res = audit_kit_project(OUTPUT_DIR, video_path=video_out)
    audit_json_path = OUTPUT_DIR / "audit_result.json"
    audit_json_path.write_text(json.dumps(audit_res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   -> Kết quả Audit: {audit_res['total_score']}/100 - Passed: {audit_res['passed']}")
    print(json.dumps(audit_res["checks"], ensure_ascii=False, indent=2))

    t_end = time.time()
    print(f"=== HOÀN TẤT TRONG {t_end - t0:.1f} GIÂY ===")
    return video_out, contact_sheet_path, audit_json_path, audit_res


if __name__ == "__main__":
    render_demo()
