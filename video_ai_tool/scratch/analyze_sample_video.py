import sys
import os
import subprocess
from pathlib import Path
import imageio_ffmpeg
from PIL import Image

ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
video = "C:/Users/admin/.gemini/antigravity/brain/9c8d69ff-e905-4ac2-97dc-25baf1a541df/.user_uploaded/media_1793594352181_f4cbee47.mp4"
out_dir = Path("output/sample_analysis")
out_dir.mkdir(parents=True, exist_ok=True)

# 1. Extract 1 frame per second
frame_pattern = out_dir / "frame_%02d.jpg"
cmd_extract = [
    ffmpeg, "-y",
    "-i", video,
    "-vf", "fps=1.0",
    str(frame_pattern)
]
subprocess.run(cmd_extract, check=True)

frames = sorted(out_dir.glob("frame_*.jpg"))
print(f"Extracted {len(frames)} frames at 1 fps.")

# 2. Build contact sheet
# 38 frames -> 6 columns x 7 rows (or 8 cols x 5 rows)
n_cols = 6
n_rows = (len(frames) + n_cols - 1) // n_cols
thumb_w = 240
thumb_h = int(thumb_w * 1280 / 720) # 426
contact_im = Image.new("RGB", (n_cols * thumb_w, n_rows * thumb_h), (20, 20, 20))

for idx, f in enumerate(frames):
    col = idx % n_cols
    row = idx // n_cols
    with Image.open(f) as im:
        thumb = im.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        contact_im.paste(thumb, (col * thumb_w, row * thumb_h))

contact_path = out_dir / "sample_contact_sheet.jpg"
contact_im.save(str(contact_path), quality=85)
print(f"Contact sheet saved to: {contact_path}")

# 3. Detect scene cuts
cmd_scenes = [
    ffmpeg,
    "-i", video,
    "-filter_complex", "select='gt(scene,0.25)',metadata=print:file=-",
    "-f", "null", "-"
]
res_scenes = subprocess.run(cmd_scenes, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, errors="ignore")
print("Scene cut stdout output:")
cut_times = []
for line in res_scenes.stdout.splitlines():
    if "pts_time:" in line:
        t = line.split("pts_time:")[1].strip()
        cut_times.append(float(t))
print("Detected cut times:", cut_times)
