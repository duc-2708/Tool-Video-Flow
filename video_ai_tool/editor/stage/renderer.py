"""Stage Engine Playwright renderer -> FFmpeg MP4 output."""
import base64
import json
import math
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryFile
from typing import Any, Dict, Optional, Tuple

from imageio_ffmpeg import get_ffmpeg_exe
from PIL import Image

from editor.stage.compiler import build_stage_html, compile_stage_script
from editor.stage.schema import StageScript


@contextmanager
def stage_browser_page(size: Tuple[int, int]):
    """Launch headless Chromium for Stage Engine frame captures."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(
            headless=True,
            timeout=25000,
            args=["--disable-gpu", "--disable-lcd-text", "--force-color-profile=srgb"]
        )
        try:
            context = browser.new_context(
                viewport={"width": size[0], "height": size[1]},
                device_scale_factor=1,
                locale="vi-VN",
                color_scheme="dark",
                reduced_motion="reduce"
            )
            context.route("**/*", lambda route: route.abort() if route.request.url.startswith("http") else route.continue_())
            page = context.new_page()
            page.set_default_timeout(15000)
            yield page
        finally:
            browser.close()


def render_stage_script(
    script: StageScript,
    output_mp4: Path,
    *,
    scale: float = 0.5,
    fps: int = 24,
    words_data: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Any] = None
) -> Dict[str, Any]:
    """Render StageScript to MP4 video and contact sheet."""
    compiled_script = compile_stage_script(script, words_data)
    html_content = build_stage_html(compiled_script)

    base_w, base_h = 1080, 1920
    render_w = int(base_w * scale)
    render_h = int(base_h * scale)
    # Ensure even dimensions for FFmpeg
    render_w = render_w if render_w % 2 == 0 else render_w + 1
    render_h = render_h if render_h % 2 == 0 else render_h + 1

    total_duration = sum(sc.duration_sec for sc in compiled_script.scenes)
    total_duration = max(1.0, total_duration)
    total_frames = max(1, math.ceil(total_duration * fps))

    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    temp_mp4 = output_mp4.with_suffix(".tmp.mp4")

    started = time.perf_counter()
    sample_frames = []
    sample_interval = max(1, total_frames // 12)
    layout_audit = {}

    with stage_browser_page((render_w, render_h)) as page, TemporaryFile() as errors:
        # Load HTML
        page.set_content(html_content, wait_until="load")
        page.evaluate("() => document.fonts.ready")
        page.evaluate("() => window.renderAt(0)")

        # Collect initial layout audit
        layout_audit = page.evaluate("() => window.getLayoutAudit ? window.getLayoutAudit() : {}")

        # Launch FFmpeg process
        cmd = [
            get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "image2pipe", "-vcodec", "mjpeg", "-framerate", str(fps),
            "-i", "pipe:0", "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(temp_mp4)
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errors)

        try:
            for frame_idx in range(total_frames):
                t = min(frame_idx / fps, total_duration - 1e-5)
                page.evaluate(f"t => window.renderAt({t})")
                frame_bytes = page.screenshot(type="jpeg", quality=90, animations="disabled")
                proc.stdin.write(frame_bytes)

                if frame_idx % sample_interval == 0 and len(sample_frames) < 12:
                    sample_frames.append(frame_bytes)

                if progress_callback and frame_idx % 20 == 0:
                    progress_callback(frame_idx / total_frames, f"Stage Engine: {frame_idx}/{total_frames} frames")

            proc.stdin.close()
            proc.wait(timeout=60)
            if proc.returncode != 0:
                errors.seek(0)
                raise RuntimeError(f"FFmpeg error: {errors.read().decode('utf-8', errors='ignore')}")

            if temp_mp4.is_file():
                temp_mp4.replace(output_mp4)
        finally:
            if proc.poll() is None:
                proc.kill()
            if temp_mp4.is_file():
                temp_mp4.unlink(missing_ok=True)

    elapsed = time.perf_counter() - started

    # Generate contact sheet
    contact_sheet_path = output_mp4.parent / "contact_sheet.png"
    if sample_frames:
        from io import BytesIO
        images = [Image.open(BytesIO(b)) for b in sample_frames]
        cols = 4
        rows = math.ceil(len(images) / cols)
        cell_w, cell_h = images[0].size
        sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (9, 4, 26))
        for idx, img in enumerate(images):
            c = idx % cols
            r = idx // cols
            sheet.paste(img, (c * cell_w, r * cell_h))
        sheet.save(contact_sheet_path, "PNG")

    return {
        "output_path": str(output_mp4),
        "contact_sheet": str(contact_sheet_path),
        "total_frames": total_frames,
        "duration_sec": total_duration,
        "render_seconds": round(elapsed, 2),
        "fps": fps,
        "scale": scale,
        "width": render_w,
        "height": render_h,
        "layout_audit": layout_audit
    }
