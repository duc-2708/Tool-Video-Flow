"""Render 38s Light Glass Style Demo Video (6 recipes, 30fps, 1080x1920) offline."""
import io
import json
import math
import subprocess
import time
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image, ImageDraw, ImageFont
from imageio_ffmpeg import get_ffmpeg_exe
from playwright.sync_api import sync_playwright

from pipeline.render_motion import html_document

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "output" / "light_glass_demo"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEMO_SHOTS = [
    {
        "id": 1,
        "recipe": "lg_source_headline",
        "start": 0.0,
        "duration": 6.0,
        "source_domain": "theverge.com",
        "narration": "Kiến trúc chip xử lý thế hệ mới vừa được công bố với quy trình đóng gói tiên tiến.",
        "data": {
            "source": "THE VERGE · 2 GIỜ TRƯỚC",
            "title": "KIẾN TRÚC VI XỬ LÝ MỚI ĐẠT ĐỘT PHÁ VƯỢT TRỘI",
            "highlight": ["VI XỬ LÝ", "ĐỘT PHÁ"],
            "text": "Kiến trúc chip thế hệ mới vừa được công bố với quy trình đóng gói tiên tiến.",
        }
    },
    {
        "id": 2,
        "recipe": "lg_stat_hero",
        "start": 6.0,
        "duration": 6.0,
        "source_domain": "theverge.com",
        "narration": "Hiệu năng xử lý các tác vụ trí tuệ nhân tạo tăng vọt 78% so với thế hệ tiền nhiệm.",
        "data": {
            "label": "HIỆU NĂNG TÁC VỤ TRÍ TUỆ NHÂN TẠO",
            "value": 78,
            "unit": "%",
            "number_text": "78%",
            "text": "Hiệu năng xử lý các tác vụ trí tuệ nhân tạo tăng vọt 78% so với thế hệ trước.",
        }
    },
    {
        "id": 3,
        "recipe": "lg_shot_features",
        "start": 12.0,
        "duration": 7.0,
        "source_domain": "theverge.com",
        "narration": "Ba điểm nâng cấp mấu chốt bao gồm băng thông mở rộng, tiết kiệm pin và hỗ trợ toàn diện.",
        "data": {
            "title": "3 ĐIỂM NÂNG CẤP MẤU CHỐT",
            "items": [
                "Băng thông bộ nhớ mở rộng gấp đôi cho mô hình AI",
                "Tiêu thụ năng lượng giảm 35% giúp kéo dài thời lượng pin",
                "Tương thích hoàn toàn hệ điều hành và framework hiện nay"
            ],
            "text": "Ba điểm nâng cấp mấu chốt bao gồm băng thông mở rộng, tiết kiệm pin và hỗ trợ toàn diện."
        }
    },
    {
        "id": 4,
        "recipe": "lg_vs_compare",
        "start": 19.0,
        "duration": 7.0,
        "source_domain": "theverge.com",
        "narration": "So với thế hệ cũ chỉ có 14 nhân, thế hệ mới mang tới 24 nhân xử lý với điện áp tối ưu.",
        "data": {
            "title": "ĐỐI CHIẾU HAI THẾ HỆ VI XỬ LÝ",
            "bars": [
                {"label": "Thế hệ cũ: 14 nhân xử lý, tiêu thụ 65W", "value": 45},
                {"label": "Thế hệ mới: 24 nhân xử lý, tiêu thụ 38W", "value": 85}
            ],
            "text": "So với thế hệ cũ chỉ có 14 nhân, thế hệ mới mang tới 24 nhân xử lý với điện áp tối ưu."
        }
    },
    {
        "id": 5,
        "recipe": "lg_note_card",
        "start": 26.0,
        "duration": 6.0,
        "source_domain": "theverge.com",
        "narration": "Giới chuyên gia nhận định đây là bước nhảy vọt quan trọng nhất của ngành phần cứng năm nay.",
        "data": {
            "label": "GHI CHÚ CHUYÊN GIA",
            "text": "Bước nhảy vọt quan trọng nhất của toàn bộ ngành công nghiệp bán dẫn trong năm nay.",
            "author": "Báo cáo phân tích phần cứng · Mẫu"
        }
    },
    {
        "id": 6,
        "recipe": "lg_cta_profile",
        "start": 32.0,
        "duration": 6.0,
        "source_domain": "theverge.com",
        "narration": "Theo dõi kênh để đón nhận các thông tin công nghệ và trí tuệ nhân tạo cập nhật mỗi ngày.",
        "data": {
            "text": "BẤM THEO DÕI ĐỂ CẬP NHẬT TIN CÔNG NGHỆ VÀ TRÍ TUỆ NHÂN TẠO MỚI NHẤT MỖI NGÀY",
            "channel_name": "TIN CÔNG NGHỆ",
            "channel_handle": "@tincongnghe_ai"
        }
    }
]


def build_demo_payload() -> dict:
    total_dur = 38.0
    shots = []
    for s in DEMO_SHOTS:
        shots.append({
            "start": s["start"],
            "duration": s["duration"],
            "template": s["recipe"],
            "source_domain": s["source_domain"],
            "data": s["data"],
            "beats": [
                {"at_sec": round(s["start"] + 0.35, 2), "action": f"enter_{s['recipe']}"},
                {"at_sec": round(s["start"] + 1.5, 2), "action": f"action_{s['recipe']}_step"}
            ],
            "visual_plan": {
                "scene_type": s["recipe"],
                "recipe": s["recipe"],
                "depth_3d": False,
                "data": s["data"],
                "beats": [
                    {"at_sec": 0.35, "action": f"enter_{s['recipe']}"},
                    {"at_sec": 1.5, "action": f"action_{s['recipe']}_step"}
                ]
            }
        })

    payload = {
        "width": 1080,
        "height": 1920,
        "duration": total_dur,
        "theme": {
            "name": "light_glass",
            "top": "#f4f5f8",
            "bottom": "#e8ecf2",
            "card": "#ffffff",
            "foreground": "#1a1446",
            "accent": "#2563eb",
            "secondary": "#3d2bb0"
        },
        "brand_name": "TIN CÔNG NGHỆ",
        "brand_label": "BẢN TIN CÔNG NGHỆ",
        "brand_logo_path": "",
        "brand_logo_data_uri": "",
        "source_domain": "theverge.com",
        "captions": {"enabled": False},
        "shots": shots,
        "words": [],
        "caption_words": []
    }
    return payload


def create_contact_sheet(image_paths: list[Path], output_path: Path):
    """Combine 6 mid-frame screenshots into a clean 2x3 contact sheet."""
    images = [Image.open(p) for p in image_paths]
    thumb_w, thumb_h = 360, 640
    cols, rows = 3, 2
    pad = 20
    header_h = 80
    sheet_w = cols * thumb_w + (cols + 1) * pad
    sheet_h = rows * thumb_h + (rows + 1) * pad + header_h

    sheet = Image.new("RGB", (sheet_w, sheet_h), "#f4f5f8")
    draw = ImageDraw.Draw(sheet)

    # Title header
    draw.text((pad, 25), "PHONG CÁCH LIGHT GLASS — BẢNG TỔNG QUAN 6 SHOTS (CONTACT SHEET)", fill="#1a1446")

    labels = [
        "Shot 1: lg_source_headline (t=3.0s)",
        "Shot 2: lg_stat_hero (t=9.0s)",
        "Shot 3: lg_shot_features (t=15.5s)",
        "Shot 4: lg_vs_compare (t=22.5s)",
        "Shot 5: lg_note_card (t=29.0s)",
        "Shot 6: lg_cta_profile (t=35.0s)",
    ]

    for idx, img in enumerate(images):
        c = idx % cols
        r = idx // cols
        x = pad + c * (thumb_w + pad)
        y = header_h + pad + r * (thumb_h + pad)

        resized = img.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        sheet.paste(resized, (x, y))
        draw.rectangle([x, y, x + thumb_w, y + thumb_h], outline="#e2e8f0", width=2)
        draw.text((x + 8, y + 8), labels[idx], fill="#2563eb")

    sheet.save(output_path, "PNG")
    print(f"Contact sheet saved to {output_path}")


def main():
    print("[*] Bat dau dung video Light Glass Demo (38s, 6 shots, 30fps)...")
    t0 = time.time()
    payload = build_demo_payload()
    fps = 30
    total_frames = int(payload["duration"] * fps)
    font_path = PROJECT_ROOT / "assets" / "fonts" / "Inter-Regular.ttf"
    html_content = html_document(payload, str(font_path))

    html_file = OUTPUT_DIR / "demo_stage.html"
    html_file.write_text(html_content, encoding="utf-8")

    mp4_dest = OUTPUT_DIR / "light_glass_demo.mp4"
    mid_images = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-gpu", "--disable-lcd-text", "--force-color-profile=srgb"]
        )
        context = browser.new_context(
            viewport={"width": 1080, "height": 1920},
            device_scale_factor=1,
            locale="vi-VN",
            reduced_motion="reduce"
        )
        page = context.new_page()
        page.set_content(html_content, wait_until="load")
        page.evaluate("() => document.fonts.ready")

        print("[*] Xuat 6 khung hinh giua tung shot (mid-frames)...")
        mid_times = [3.0, 9.0, 15.5, 22.5, 29.0, 35.0]
        for idx, mt in enumerate(mid_times, start=1):
            page.evaluate(f"() => window.renderAt({mt})")
            out_img = OUTPUT_DIR / f"shot_{idx}_mid.png"
            page.screenshot(path=str(out_img), type="png")
            mid_images.append(out_img)
            print(f"  - Shot {idx} (t={mt}s) -> {out_img.name}")

        create_contact_sheet(mid_images, OUTPUT_DIR / "contact_sheet.png")

        print(f"[*] Bat dau render {total_frames} khung hinh vao ffmpeg...", flush=True)
        ffmpeg_cmd = [
            get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "image2pipe", "-vcodec", "mjpeg", "-framerate", str(fps), "-i", "pipe:0",
            "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4_dest)
        ]
        proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        for f in range(total_frames):
            t = f / fps
            page.evaluate(f"() => window.renderAt({t})")
            frame_bytes = page.screenshot(type="jpeg", quality=80)
            proc.stdin.write(frame_bytes)
            if (f + 1) % 60 == 0 or f == total_frames - 1:
                pct = int((f + 1) / total_frames * 100)
                elapsed = round(time.time() - t0, 1)
                fps_actual = round((f + 1) / max(0.1, elapsed), 1)
                print(f"  Progress: {f + 1}/{total_frames} frames ({pct}%) - {elapsed}s ({fps_actual} fps)", flush=True)

        proc.stdin.close()
        proc.wait()
        browser.close()

    total_time = round(time.time() - t0, 1)
    print(f"[OK] Hoan thanh dung video demo: {mp4_dest} ({total_time}s)", flush=True)


if __name__ == "__main__":
    main()
