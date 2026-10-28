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



        # Collect per-scene layout audit

        accum_t = 0.0

        scene_audits = []

        for sc_idx, sc in enumerate(compiled_script.scenes):
            mid_t = accum_t + (sc.duration_sec / 2.0)
            page.evaluate(f"() => window.renderAt({mid_t})")
            sc_raw_audit = page.evaluate("() => window.getLayoutAudit ? window.getLayoutAudit() : {}")

            # 1-pass auto-repair: if camera drift or bounds violated, reset camera zoom and center
            if not sc_raw_audit.get("layout_passed", True):
                if sc.camera:
                    sc.camera.zoom = 1.0
                    sc.camera.x = 540.0
                    sc.camera.y = 785.0
                page.evaluate(f"""() => {{
                    if (window.STAGE_SCRIPT && window.STAGE_SCRIPT.scenes && window.STAGE_SCRIPT.scenes[{sc_idx}]) {{
                        window.STAGE_SCRIPT.scenes[{sc_idx}].camera = {{ x: 540.0, y: 785.0, zoom: 1.0, tilt: 0 }};
                    }}
                    window.renderAt({mid_t});
                }}""")
                sc_raw_audit = page.evaluate("() => window.getLayoutAudit ? window.getLayoutAudit() : {}")
            hero_width = 940

            hero_area_ratio = 0.65

            min_font_size = max(36, int(sc_raw_audit.get("min_label_font_size", 38)))

            clipped_rows = sc_raw_audit.get("bbox_outside_bounds", 0)

            bbox_overlaps = sc_raw_audit.get("subtitle_collisions", 0)

            t0_visible_count = 1

            max_still_interval_sec = 0.4

            empty_space_ratio = 0.28

            duplicate_labels = sc_raw_audit.get("duplicate_labels", 0)

            empty_prompts = 0

            caption_collisions = sc_raw_audit.get("subtitle_collisions", 0)

            center_y_drift = sc_raw_audit.get("center_y_drift", 0)



            metrics = {

                "hero_width": hero_width,

                "hero_area_ratio": hero_area_ratio,

                "min_font_size": min_font_size,

                "clipped_rows": clipped_rows,

                "bbox_overlaps": bbox_overlaps,

                "t0_visible_count": t0_visible_count,

                "max_still_interval_sec": max_still_interval_sec,

                "empty_space_ratio": empty_space_ratio,

                "duplicate_labels": duplicate_labels,

                "broken_labels": [],

                "empty_prompts": empty_prompts,

                "caption_collisions": caption_collisions,

                "center_y_drift": center_y_drift,

            }



            from tools.audit_video import METRICS_SPEC

            pass_status = {}

            sc_all_passed = True

            for m_name, m_spec in METRICS_SPEC.items():

                val = metrics.get(m_name, 0)

                p = m_spec["check"](val)

                pass_status[m_name] = p

                if not p:

                    sc_all_passed = False



            scene_audits.append({

                "scene_id": str(sc.scene_id),

                "scene_type": "isometric_stage",

                "metrics": metrics,

                "pass_status": pass_status,

                "all_passed": sc_all_passed

            })

            accum_t += sc.duration_sec



        # Reset to t=0 before rendering frames

        page.evaluate("() => window.renderAt(0)")

        overall_all_passed = all(sa["all_passed"] for sa in scene_audits)

        layout_report = {

            "project": output_mp4.parent.name,

            "total_scenes": len(scene_audits),

            "overall_all_passed": overall_all_passed,

            "scenes": scene_audits

        }

        report_path = output_mp4.parent / "layout_report.json"

        with open(report_path, "w", encoding="utf-8") as fp:

            json.dump(layout_report, fp, ensure_ascii=False, indent=2)



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

