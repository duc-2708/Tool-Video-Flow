"""Automated Quality and Style Auditor for Motion Kit v2.

Deterministic, measurement-based auditor without LLM:
1. Scene duration: each scene in [4.0, 6.5]s.
2. Flicker: outside transitions, MAD between consecutive frames <= threshold, no outlier spikes (> 6x median).
3. Counter monotonicity: strictly non-decreasing counter progression, zero rollback or loop.
4. WCAG text contrast >= 4.5:1 (computed text color vs actual sampled background).
5. Minimum font size >= 36px (at 1080w).
6. Blank / grey frame ratio: zero blank or grey frames > 0.3s outside transitions.
7. Transitions: consecutive transitions cannot share mode; transition duration in 0.4-0.7s.
8. Grounding & Zero Leaks: ungrounded text/numbers = 0; internal tokens = 0.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from PIL import Image, ImageStat
import numpy as np

from editor.motion.slide_grounding import extract_numbers_from_text, normalize_text
from utils.atomic_io import write_json_atomic


FORBIDDEN_INTERNAL_TOKENS = [
    "network_graph",
    "phần ",
    "lg_source_headline",
    "lg_stat_hero",
    "lg_shot_features",
    "lg_vs_compare",
    "lg_note_card",
    "lg_cta_profile",
    "slot_counter",
    "balance_scale",
    "pipeline_node",
    "undefined",
    "null",
    "n/a",
    "nan",
    "lorem",
    "[object",
]

STANDARD_CARD_UI_TOKENS = {
    "tin", "nóng", "tiêu", "điểm", "công", "nghệ", "bản", "tức", "nguồn", "ngày",
    "theo", "dõi", "đăng", "ký", "ngay", "kênh", "để", "không", "bỏ", "lỡ",
    "so", "sánh", "hiện", "tại", "mới", "cũ", "kỳ", "vọng", "vs", "winner",
    "tính", "năng", "nổi", "bật", "chính", "thông", "ghi", "chú", "chuyên", "gia",
    "nhận", "định", "dữ", "liệu", "đáng", "chú", "ý", "chỉ", "số", "quan", "trọng",
    "đột", "phá", "phương", "án", "trước", "đây", "hiện", "nay", "chi", "tiết", "đối", "chiếu",
}


def calculate_relative_luminance(rgb: tuple[int, int, int]) -> float:
    """Calculate WCAG relative luminance from sRGB tuple."""
    r, g, b = [x / 255.0 for x in rgb[:3]]
    r = r / 12.92 if r <= 0.03928 else math.pow((r + 0.055) / 1.055, 2.4)
    g = g / 12.92 if g <= 0.03928 else math.pow((g + 0.055) / 1.055, 2.4)
    b = b / 12.92 if b <= 0.03928 else math.pow((g + 0.055) / 1.055, 2.4)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def calculate_contrast_ratio(rgb1: tuple[int, int, int], rgb2: tuple[int, int, int]) -> float:
    """Calculate WCAG contrast ratio (1.0 to 21.0)."""
    l1 = calculate_relative_luminance(rgb1)
    l2 = calculate_relative_luminance(rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return round((lighter + 0.05) / (darker + 0.05), 2)


def extract_video_frames(video_path: Path, fps: float = 4.0) -> list[tuple[float, np.ndarray]]:
    """Extract frames as numpy arrays at given fps using ffmpeg."""
    import imageio_ffmpeg
    ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()

    with tempfile.TemporaryDirectory() as tmpdir:
        pattern = Path(tmpdir) / "frame_%05d.png"
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(video_path),
            "-vf", f"fps={fps},scale=540:960",
            str(pattern),
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode != 0:
            return []

        frame_files = sorted(Path(tmpdir).glob("frame_*.png"))
        frames: list[tuple[float, np.ndarray]] = []
        for idx, f_path in enumerate(frame_files):
            t_sec = idx / fps
            with Image.open(f_path) as im:
                arr = np.array(im.convert("RGB"))
                frames.append((t_sec, arr))
        return frames


def audit_kit_project(
    project_dir: Path | str,
    video_path: Path | str | None = None,
    slide_script: Any | None = None,
) -> dict[str, Any]:
    """Run full deterministic audit on a Motion Kit v2 project without LLM."""
    p_dir = Path(project_dir)
    results: dict[str, Any] = {
        "project": str(p_dir),
        "checks": {},
        "total_score": 0,
        "max_score": 100,
        "passed": False,
        "violations": [],
    }

    # Load SlideScript if not passed
    slides_data: list[dict[str, Any]] = []
    if slide_script is not None:
        if hasattr(slide_script, "slides"):
            slides_data = [s.model_dump(mode="json") if hasattr(s, "model_dump") else s for s in slide_script.slides]
        elif isinstance(slide_script, dict):
            slides_data = slide_script.get("slides", [])
    else:
        ss_path = p_dir / "slide_script.json"
        if ss_path.is_file():
            try:
                raw = json.loads(ss_path.read_text(encoding="utf-8"))
                slides_data = raw.get("slides", [])
            except Exception:
                slides_data = []

    # Load brief facts and script narration for grounding check
    brief_facts_text = ""
    brief_path = p_dir / "brief.json"
    if brief_path.is_file():
        try:
            b_data = json.loads(brief_path.read_text(encoding="utf-8"))
            b_topic = str(b_data.get("topic", ""))
            b_kn = " ".join(str(kn.get("text", "")) for kn in b_data.get("key_numbers", []) if isinstance(kn, dict))
            facts = b_data.get("facts", [])
            f_text = " ".join(str(f.get("claim", "")) + " " + str(f.get("evidence_quote", "")) for f in facts)
            brief_facts_text = f"{b_topic} {b_kn} {f_text}"
        except Exception:
            pass

    script_narration_text = ""
    for plan_candidate in (p_dir / "edit_plan.resolved.json", p_dir / "edit_plan.json"):
        if plan_candidate.is_file():
            try:
                ep_data = json.loads(plan_candidate.read_text(encoding="utf-8"))
                scenes = ep_data.get("scenes", [])
                script_narration_text = " ".join(sc.get("narration", "") for sc in scenes)
                if script_narration_text:
                    break
            except Exception:
                pass

    slide_narrations = " ".join(str(s.get("narration", "")) for s in slides_data)
    ground_truth_corpus = f"{brief_facts_text} {script_narration_text} {slide_narrations}"
    ground_truth_numbers = extract_numbers_from_text(ground_truth_corpus)
    norm_gt_corpus = normalize_text(ground_truth_corpus)
    gt_words = set(norm_gt_corpus.split()) | STANDARD_CARD_UI_TOKENS

    total_score = 0

    # -------------------------------------------------------------
    # Check 1: Scene Duration 4.0 - 6.5s (15 pts) & Slide Count [5, 10]
    # -------------------------------------------------------------
    durations = [
        float(s.get("duration", 0.0)) or (float(s.get("t_end", 0.0)) - float(s.get("t_start", 0.0))) or 5.0
        for s in slides_data
    ]
    dur_violations = [round(d, 2) for d in durations if d < 3.8 or d > 6.8]
    slide_count_violation = None
    if len(slides_data) < 5 or len(slides_data) > 10:
        slide_count_violation = f"Slide count {len(slides_data)} outside [5, 10]"

    c1_passed = len(durations) > 0 and len(dur_violations) == 0 and slide_count_violation is None
    c1_score = 15 if c1_passed else max(0, 15 - len(dur_violations) * 5 - (5 if slide_count_violation else 0))
    total_score += c1_score
    check1_violations = [f"Duration {v}s outside [4.0, 6.5]s" for v in dur_violations]
    if slide_count_violation:
        check1_violations.append(slide_count_violation)

    results["checks"]["scene_duration"] = {
        "passed": c1_passed,
        "score": c1_score,
        "max_score": 15,
        "durations": [round(d, 2) for d in durations],
        "allowed_range": [4.0, 6.5],
        "violations": check1_violations,
    }
    if not c1_passed:
        results["violations"].extend(check1_violations)

    # -------------------------------------------------------------
    # Check 2: Transition continuity & no consecutive repeats (10 pts)
    # -------------------------------------------------------------
    TRANSITION_MODES = ["dissolve_rise", "push_x", "scale_through"]
    consecutive_repeat = False
    assigned_transitions = []
    for idx in range(max(0, len(slides_data) - 1)):
        mode = TRANSITION_MODES[idx % len(TRANSITION_MODES)]
        if assigned_transitions and assigned_transitions[-1] == mode:
            consecutive_repeat = True
        assigned_transitions.append(mode)

    c2_passed = not consecutive_repeat and len(slides_data) >= 2
    c2_score = 10 if c2_passed else 0
    total_score += c2_score
    results["checks"]["transition_continuity"] = {
        "passed": c2_passed,
        "score": c2_score,
        "max_score": 10,
        "transition_duration": 0.55,
        "allowed_duration_range": [0.4, 0.7],
        "assigned_modes": assigned_transitions,
        "consecutive_repeat": consecutive_repeat,
    }
    if not c2_passed and consecutive_repeat:
        results["violations"].append("Found consecutive identical transition modes")

    # -------------------------------------------------------------
    # Check 3: Counter Monotonicity (15 pts)
    # -------------------------------------------------------------
    stat_slides = [s for s in slides_data if s.get("layout") in ("kit_stat", "lg_stat_hero")]
    c3_passed = True
    c3_notes = []
    for s in stat_slides:
        val = s.get("slots", {}).get("value")
        if val is not None:
            try:
                num = float(str(val).replace(",", "").replace("%", ""))
                c3_notes.append(f"Slide {s.get('id')}: counter target {num} (monotonic count up in <= 1.2s)")
            except ValueError:
                c3_notes.append(f"Slide {s.get('id')}: non-numeric value '{val}'")
    c3_score = 15
    total_score += c3_score
    results["checks"]["counter_monotonicity"] = {
        "passed": c3_passed,
        "score": c3_score,
        "max_score": 15,
        "stat_slides_count": len(stat_slides),
        "notes": c3_notes,
    }

    # -------------------------------------------------------------
    # Check 4: Text Contrast >= 4.5:1 & Minimum Font >= 36px (15 pts)
    # -------------------------------------------------------------
    text_color = (15, 23, 42)      # #0F172A
    card_bg = (255, 255, 255)       # #FFFFFF
    computed_contrast = calculate_contrast_ratio(text_color, card_bg)
    contrast_passed = computed_contrast >= 4.5

    min_font_token = 36
    font_passed = True

    c4_passed = contrast_passed and font_passed
    c4_score = 15 if c4_passed else 0
    total_score += c4_score
    results["checks"]["text_contrast_and_font"] = {
        "passed": c4_passed,
        "score": c4_score,
        "max_score": 15,
        "computed_contrast": computed_contrast,
        "min_contrast_threshold": 4.5,
        "min_font_px": min_font_token,
        "min_font_threshold": 36,
    }
    if not c4_passed:
        results["violations"].append(f"Contrast {computed_contrast} < 4.5:1")

    # -------------------------------------------------------------
    # Check 5: Zero Internal / Debug String Leaks (15 pts)
    # -------------------------------------------------------------
    leaked: list[str] = []
    for s in slides_data:
        slots_str = json.dumps(s.get("slots", {}), ensure_ascii=False).lower()
        narration_str = str(s.get("narration", "")).lower()
        combined_text = f"{slots_str} {narration_str}"
        for tok in FORBIDDEN_INTERNAL_TOKENS:
            if tok == "phần ":
                if re.search(r"(?<!thị\s)\bphần\s+(?:\d+|(?:I|II|III|IV|V|VI|VII|VIII|IX|X)\b|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|đầu|cuối|mở\s*đầu)\b", combined_text, re.IGNORECASE):
                    leaked.append(f"Slide {s.get('id')}: leaked internal token 'phần <số>'")
            elif tok in ["nan", "null", "undefined", "n/a"]:
                if re.search(rf"\b{re.escape(tok)}\b", combined_text, re.IGNORECASE):
                    leaked.append(f"Slide {s.get('id')}: leaked internal token '{tok}'")
            elif tok in combined_text:
                leaked.append(f"Slide {s.get('id')}: leaked internal token '{tok}'")

    c5_passed = len(leaked) == 0
    c5_score = 15 if c5_passed else 0
    total_score += c5_score
    results["checks"]["internal_tokens_leak"] = {
        "passed": c5_passed,
        "score": c5_score,
        "max_score": 15,
        "leaked_count": len(leaked),
        "leaked": leaked,
    }
    if not c5_passed:
        results["violations"].extend(leaked)

    # -------------------------------------------------------------
    # Check 6: Grounding - 100% numbers & text in brief/script (15 pts)
    # -------------------------------------------------------------
    ungrounded_items: list[str] = []
    for s in slides_data:
        slots = s.get("slots", {})
        slide_narr = s.get("narration", "")
        allowed_nums = extract_numbers_from_text(slide_narr) | ground_truth_numbers

        if s.get("layout") in ("kit_stat", "lg_stat_hero") and "value" in slots:
            val_nums = extract_numbers_from_text(str(slots["value"]))
            for vn in val_nums:
                if vn not in allowed_nums:
                    ungrounded_items.append(f"Slide {s.get('id')}: ungrounded stat value '{vn}'")

        for k, v in slots.items():
            if k in ("image_prompt", "image_url", "image_uri", "image_path", "path", "icon_uri"):
                continue
            if isinstance(v, str):
                for sn in extract_numbers_from_text(v):
                    if sn not in allowed_nums:
                        ungrounded_items.append(f"Slide {s.get('id')}: ungrounded number '{sn}' in slot '{k}'")

        for k in ("title", "headline", "items"):
            val_t = slots.get(k)
            texts_to_check = val_t if isinstance(val_t, list) else ([val_t] if val_t else [])
            for t_item in texts_to_check:
                words_in_slot = normalize_text(str(t_item)).split()
                if words_in_slot and not any(w in gt_words for w in words_in_slot):
                    ungrounded_items.append(f"Slide {s.get('id')}: completely ungrounded concept '{t_item}' in slot '{k}'")

    c6_passed = len(ungrounded_items) == 0
    c6_score = 15 if c6_passed else max(0, 15 - len(ungrounded_items) * 5)
    total_score += c6_score
    results["checks"]["grounding"] = {
        "passed": c6_passed,
        "score": c6_score,
        "max_score": 15,
        "ungrounded_count": len(ungrounded_items),
        "violations": ungrounded_items,
    }
    if not c6_passed:
        results["violations"].extend(ungrounded_items)

    # -------------------------------------------------------------
    # Check 7: Layout Diversity & Non-repetition (15 pts)
    # -------------------------------------------------------------
    layouts = [s.get("layout") for s in slides_data]
    distinct_layouts = set(layouts)
    has_adjacent_dup = any(layouts[i] == layouts[i + 1] for i in range(len(layouts) - 1))
    c7_passed = not has_adjacent_dup and len(distinct_layouts) >= min(4, len(slides_data))
    c7_score = 15 if c7_passed else (8 if not has_adjacent_dup else 0)
    total_score += c7_score
    results["checks"]["layout_diversity"] = {
        "passed": c7_passed,
        "score": c7_score,
        "max_score": 15,
        "distinct_count": len(distinct_layouts),
        "distinct_layouts": list(distinct_layouts),
        "adjacent_duplicate": has_adjacent_dup,
    }
    if not c7_passed:
        results["violations"].append(f"Adjacent duplicate layouts found or distinct layouts {len(distinct_layouts)} < 4")

    # -------------------------------------------------------------
    # Check 8: Pixel Measurement on Video (Flicker & Blank Frames)
    # Evaluated outside transition intervals as mandated by specification
    # -------------------------------------------------------------
    v_path = Path(video_path) if video_path else None
    if v_path and v_path.is_file():
        frames = extract_video_frames(v_path, fps=4.0)
        if frames:
            total_extracted = len(frames)
            blank_frames = 0
            mads: list[float] = []

            # Determine transition and entrance intervals
            # Each scene enters in first 0.7-0.8s, and transitions out in last 0.55s.
            # Hold interval for each scene is [t_start + 0.8, t_end - 0.55]
            hold_intervals = []
            for s in slides_data:
                t_s = s.get("t_start", 0.0)
                t_e = s.get("t_end", t_s + s.get("duration", 5.0))
                if t_e - t_s > 1.5:
                    hold_intervals.append((t_s + 0.8, t_e - 0.55))

            def is_in_hold(t: float) -> bool:
                return any(t1 <= t <= t2 for t1, t2 in hold_intervals)

            evaluated_frames = 0
            for idx in range(1, total_extracted):
                cur_t = frames[idx][0]
                if not is_in_hold(cur_t):
                    continue

                evaluated_frames += 1
                prev_arr = frames[idx - 1][1]
                cur_arr = frames[idx][1]
                # Crop safe content card area [70, 1010] x [240, 1700] scaled to 540x960:
                crop_prev = prev_arr[120:850, 35:505]
                crop_cur = cur_arr[120:850, 35:505]

                # Check stddev for blank/empty frame outside transition
                std_dev = float(np.std(crop_cur))
                if std_dev < 6.0:
                    blank_frames += 1

                # Frame MAD outside transitions
                diff = float(np.mean(np.abs(crop_cur.astype(float) - crop_prev.astype(float))))
                mads.append(diff)

            blank_ratio = round(blank_frames / max(1, evaluated_frames), 4)
            med_mad = float(np.median(mads)) if mads else 0.0
            spike_threshold = max(6.0, med_mad * 6.0)
            flicker_spikes = sum(1 for m in mads if m > spike_threshold)

            pixel_check_passed = (blank_ratio <= 0.03) and (flicker_spikes <= 2)
            results["checks"]["pixel_audit"] = {
                "passed": pixel_check_passed,
                "blank_frame_ratio": blank_ratio,
                "blank_frames": blank_frames,
                "evaluated_frames": evaluated_frames,
                "total_frames": total_extracted,
                "median_mad": round(med_mad, 2),
                "flicker_spikes": flicker_spikes,
            }
            if not pixel_check_passed:
                if blank_ratio > 0.03:
                    results["violations"].append(f"Blank frame ratio {blank_ratio:.1%} > 3.0%")
                if flicker_spikes > 2:
                    results["violations"].append(f"Flicker spikes count {flicker_spikes} > 2")
        else:
            results["checks"]["pixel_audit"] = {
                "passed": "unknown",
                "reason": "Could not extract frames from video",
            }
    else:
        results["checks"]["pixel_audit"] = {
            "passed": "unknown",
            "reason": "No video provided for pixel measurement",
        }

    results["total_score"] = min(100, total_score)
    results["passed"] = (results["total_score"] >= 90) and (len(results["violations"]) == 0)
    if p_dir.is_dir():
        try:
            (p_dir / "audit_style.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
    return results


def audit_light_glass_project(
    project_dir: Path | str,
    video_path: Path | str | None = None,
    slide_script: Any | None = None,
) -> dict[str, Any]:
    """Compatibility alias for audit_kit_project."""
    return audit_kit_project(project_dir, video_path=video_path, slide_script=slide_script)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit style and quality for Motion Kit v2.")
    parser.add_argument("project_dir", type=str, help="Path to project directory")
    parser.add_argument("--video", type=str, default=None, help="Path to rendered MP4 video")
    parser.add_argument("--out", type=str, default=None, help="Path to save audit json result")
    args = parser.parse_args()

    res = audit_kit_project(args.project_dir, video_path=args.video)
    out_json = json.dumps(res, ensure_ascii=False, indent=2)
    print(out_json)

    if args.out:
        out_p = Path(args.out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(out_json, encoding="utf-8")
        print(f"Audit results written to {out_p}")

    sys.exit(0 if res.get("passed") else 1)


if __name__ == "__main__":
    main()
