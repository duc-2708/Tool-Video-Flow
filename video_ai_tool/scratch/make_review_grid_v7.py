import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ai_images_dir = ROOT / "output/auto-cong-nghe-f4d9a86b/assets/ai_images"

image_files = sorted(list(ai_images_dir.glob("beat_*.png")))
print(f"Found {len(image_files)} beat images.")

cols = 4
rows = 3
cell_w, cell_h = 360, 360
header_h = 40
canvas_w = cols * cell_w
canvas_h = rows * (cell_h + header_h)

grid = Image.new("RGB", (canvas_w, canvas_h), (15, 23, 42))
draw = ImageDraw.Draw(grid)

try:
    font = ImageFont.truetype(str(ROOT / "assets/fonts/Inter-Bold.ttf"), 20)
except Exception:
    font = ImageFont.load_default()

titles = [
    "Beat 1: Elon Keynote Stage",
    "Beat 2: Piggy Bank Cracking",
    "Beat 3: Gigafactory Robot",
    "Beat 4: Candlestick Terminal",
    "Beat 5: Cash vs Microchip",
    "Beat 6: Cashflow Golden Key",
    "Beat 7: Ted Jenkin Article",
    "Beat 8: Cyber Risk Shield",
    "Beat 9: Wealth Balance Scale",
    "Beat 10: Future AI City",
    "Beat 11: Emergency Safe Gauge",
    "Beat 12: Modern Creator CTA",
]

for idx, img_path in enumerate(image_files[:12]):
    col = idx % cols
    row = idx // cols
    x = col * cell_w
    y = row * (cell_h + header_h)

    # Draw header banner
    draw.rectangle([x, y, x + cell_w, y + header_h], fill=(30, 41, 59))
    title_text = titles[idx] if idx < len(titles) else f"Beat {idx+1}"
    draw.text((x + 10, y + 10), title_text, font=font, fill=(255, 255, 255))

    # Resize image to thumbnail
    with Image.open(img_path) as im:
        thumb = im.resize((cell_w, cell_h), Image.Resampling.LANCZOS)
        grid.paste(thumb, (x, y + header_h))

out_path = Path("C:/Users/admin/.gemini/antigravity/brain/9c8d69ff-e905-4ac2-97dc-25baf1a541df/review_grid_12_beats_v7.jpg")
grid.save(out_path, "JPEG", quality=92)
print(f"Saved contact sheet to {out_path}")
