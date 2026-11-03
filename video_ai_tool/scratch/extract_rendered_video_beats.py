import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
video_path = ROOT / "output/auto-cong-nghe-f4d9a86b/render/elon-musk-noi-tiet-kiem-tien-la-vo-nghia_tiktok_final.mp4"
tmp_dir = ROOT / "output/auto-cong-nghe-f4d9a86b/review_frames_v7"
tmp_dir.mkdir(parents=True, exist_ok=True)

timestamps = [2.0, 6.5, 11.0, 15.5, 20.0, 24.5, 29.0, 33.5, 38.0, 42.5, 47.0, 51.5]
frame_files = []

for idx, ts in enumerate(timestamps):
    out_f = tmp_dir / f"beat_{idx+1:02d}_{ts:.1f}s.png"
    cmd = [
        "ffmpeg", "-y", "-ss", str(ts), "-i", str(video_path),
        "-vframes", "1", "-vf", "scale=360:640", str(out_f)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    frame_files.append(out_f)

print(f"Extracted {len(frame_files)} video frames.")

# Create a 4x3 review contact sheet
cols = 4
rows = 3
w, h = 360, 640
header_h = 36
grid = Image.new("RGB", (cols * w, rows * (h + header_h)), (15, 23, 42))
draw = ImageDraw.Draw(grid)

try:
    font = ImageFont.truetype(str(ROOT / "assets/fonts/Inter-Bold.ttf"), 18)
except Exception:
    font = ImageFont.load_default()

labels = [
    "Beat 1 (2.0s): Keynote Stage",
    "Beat 2 (6.5s): Piggy Bank Coin",
    "Beat 3 (11.0s): Gigafactory Robot",
    "Beat 4 (15.5s): Candlestick Desk",
    "Beat 5 (20.0s): Cash vs Chip",
    "Beat 6 (24.5s): Cashflow Key",
    "Beat 7 (29.0s): Ted Jenkin Quote",
    "Beat 8 (33.5s): Cyber Risk Shield",
    "Beat 9 (38.0s): Wealth Balance",
    "Beat 10 (42.5s): Future AI City",
    "Beat 11 (47.0s): Emergency Gauge",
    "Beat 12 (51.5s): Channel CTA Card",
]

for idx, (f_path, lbl) in enumerate(zip(frame_files, labels)):
    col = idx % cols
    row = idx // cols
    x = col * w
    y = row * (h + header_h)

    draw.rectangle([x, y, x + w, y + header_h], fill=(30, 41, 59))
    draw.text((x + 8, y + 8), lbl, font=font, fill=(255, 255, 255))

    with Image.open(f_path) as im:
        grid.paste(im, (x, y + header_h))

artifact_path = Path("C:/Users/admin/.gemini/antigravity/brain/9c8d69ff-e905-4ac2-97dc-25baf1a541df/contact_sheet_rendered_video_v7.jpg")
grid.save(artifact_path, "JPEG", quality=90)
print(f"Saved contact sheet of rendered video to {artifact_path}")
