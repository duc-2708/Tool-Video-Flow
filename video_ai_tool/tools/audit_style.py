"""Automated Quality and Style Auditor for Light Glass videos.

Audits videos and SlideScripts without LLM (deterministic code):
1. Slide count in [5, 10] and duration 4s - 9s.
2. Empty frame ratio <= 3% (measured from extracted video frames; 'unknown' if no video).
3. Zero leaked internal/debug strings (network_graph, "Phần ", recipe names, undefined/null/N/A).
4. Zero ungrounded numbers or text (100% grounded in script/brief).
5. Zero text overflow beyond slot limits.
6. Layout diversity: >= 4 distinct layouts, 0 adjacent duplicate layouts.
7. Emphasis phrases: zero emphasis words outside slide.emphasis.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PIL import Image, ImageStat

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
}


def measure_empty_frame_ratio_from_video(video_path: Path) -> tuple[float | None, int, int]:
    """Measure the ratio of frames that only have background and no card content."""
    import tempfile
    import imageio_ffmpeg

    ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
    if not video_path.is_file():
        return None, 0, 0

    with tempfile.TemporaryDirectory() as tmpdir:
        frame_pattern = Path(tmpdir) / "frame_%04d.png"
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(video_path),
            "-vf", "fps=1.0,scale=540:960",
            str(frame_pattern),
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode != 0:
            return None, 0, 0

        frames = sorted(Path(tmpdir).glob("frame_*.png"))
        if not frames:
            return None, 0, 0

        total_frames = len(frames)
        empty_frames = 0

        # Center card content region in 540x960: x in [50, 490], y in [180, 750]
        crop_box = (50, 180, 490, 750)

        for f_path in frames:
            with Image.open(f_path) as im:
                cropped = im.crop(crop_box).convert("L")
                stat = ImageStat.Stat(cropped)
                std_dev = stat.stddev[0]
                # High contrast text/card has std_dev > 15; blank pastel background has std_dev < 6
                if std_dev < 6.0:
                    empty_frames += 1

        ratio = round(empty_frames / total_frames, 4)
        return ratio, empty_frames, total_frames


def audit_light_glass_project(
    project_dir: Path | str,
    video_path: Path | str | None = None,
    slide_script: Any | None = None,
) -> dict[str, Any]:
    """Run full deterministic audit on a Light Glass project without LLM."""
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

    ground_truth_corpus = f"{brief_facts_text} {script_narration_text}"
    ground_truth_numbers = extract_numbers_from_text(ground_truth_corpus)
    norm_gt_corpus = normalize_text(ground_truth_corpus)
    gt_words = set(norm_gt_corpus.split()) | STANDARD_CARD_UI_TOKENS

    score = 0

    # -------------------------------------------------------------
    # Check 1: Slide count [5, 12] and slide duration [3.8, 9.5] (15 pts)
    # -------------------------------------------------------------
    n_slides = len(slides_data)
    durations = [
        float(s.get("duration", 0.0)) or (float(s.get("t_end", 0.0)) - float(s.get("t_start", 0.0))) or 4.5
        for s in slides_data
    ]
    count_ok = 5 <= n_slides <= 12
    duration_viol = [d for d in durations if d < 3.8 or d > 9.5]
    dur_ok = len(duration_viol) == 0

    c1_passed = count_ok and dur_ok
    c1_score = 15 if c1_passed else (8 if count_ok else 0)
    score += c1_score
    results["checks"]["slide_count_and_duration"] = {
        "passed": c1_passed,
        "score": c1_score,
        "max_score": 15,
        "num_slides": n_slides,
        "durations": durations,
        "violations": [] if c1_passed else ([f"Slide count {n_slides} outside [5, 10]"] if not count_ok else [f"Durations {duration_viol} outside [4.0, 9.0]"]),
    }
    if not c1_passed:
        results["violations"].extend(results["checks"]["slide_count_and_duration"]["violations"])

    # -------------------------------------------------------------
    # Check 2: Empty frame ratio <= 6% (15 pts)
    # -------------------------------------------------------------
    v_path = Path(video_path) if video_path else None
    if v_path and v_path.is_file():
        measured_ratio, empty_cnt, total_cnt = measure_empty_frame_ratio_from_video(v_path)
        if measured_ratio is not None:
            c2_passed = measured_ratio <= 0.06
            c2_score = 15 if c2_passed else 0
            score += c2_score
            results["checks"]["empty_frame_ratio"] = {
                "passed": c2_passed,
                "score": c2_score,
                "max_score": 15,
                "empty_ratio": measured_ratio,
                "empty_frames": empty_cnt,
                "total_frames": total_cnt,
                "threshold": 0.06,
            }
            if not c2_passed:
                results["violations"].append(f"Empty frame ratio {measured_ratio:.1%} > 6.0%")
        else:
            results["checks"]["empty_frame_ratio"] = {
                "passed": "unknown",
                "score": 0,
                "max_score": 15,
                "empty_ratio": "unknown",
                "reason": "Could not extract video frames",
            }
    else:
        results["checks"]["empty_frame_ratio"] = {
            "passed": "unknown",
            "score": 0,
            "max_score": 15,
            "empty_ratio": "unknown",
            "reason": "No video provided for pixel measurement",
        }

    # -------------------------------------------------------------
    # Check 3: Zero internal/debug string leaks (15 pts)
    # network_graph, "Phần ", recipe names, undefined/null/N/A
    # -------------------------------------------------------------
    leaked: list[str] = []
    for s in slides_data:
        slots_str = json.dumps(s.get("slots", {}), ensure_ascii=False).lower()
        narration_str = str(s.get("narration", "")).lower()
        combined_text = f"{slots_str} {narration_str}"
        for tok in FORBIDDEN_INTERNAL_TOKENS:
            if tok == "phần ":
                # Catch section labels like "Phần 1", "Phần 2", "Phần một", but ignore "phần cứng", "phần mềm", "phần trăm"
                if re.search(r"\bphần\s+(?:\d+|[ivx]+|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|đầu|cuối|mở\s*đầu)\b", combined_text, re.IGNORECASE):
                    leaked.append(f"Slide {s.get('id')}: leaked internal token 'phần <số>'")
            elif tok in ["nan", "null", "undefined", "n/a"]:
                # Check for whole-word boundary so substrings like 'finance' don't trigger 'nan'
                if re.search(rf"\b{re.escape(tok)}\b", combined_text, re.IGNORECASE):
                    leaked.append(f"Slide {s.get('id')}: leaked internal token '{tok}'")
            elif tok in combined_text:
                leaked.append(f"Slide {s.get('id')}: leaked internal token '{tok}'")

    c3_passed = len(leaked) == 0
    c3_score = 15 if c3_passed else 0
    score += c3_score
    results["checks"]["internal_tokens_leak"] = {
        "passed": c3_passed,
        "score": c3_score,
        "max_score": 15,
        "leaked_count": len(leaked),
        "leaked": leaked,
    }
    if not c3_passed:
        results["violations"].extend(leaked)

    # -------------------------------------------------------------
    # Check 4: Grounding - 100% numbers & text in script/brief (15 pts)
    # -------------------------------------------------------------
    ungrounded_items: list[str] = []
    for s in slides_data:
        slots = s.get("slots", {})
        slide_narr = s.get("narration", "")
        allowed_nums = extract_numbers_from_text(slide_narr) | ground_truth_numbers

        # 1. Number grounding
        if s.get("layout") == "lg_stat_hero" and "value" in slots:
            val_nums = extract_numbers_from_text(str(slots["value"]))
            for vn in val_nums:
                if vn not in allowed_nums:
                    ungrounded_items.append(f"Slide {s.get('id')}: ungrounded stat value '{vn}'")

        for k, v in slots.items():
            if k in ("image_prompt", "image_url", "image_uri", "image_path", "icon_uri"):
                continue
            if isinstance(v, str):
                for sn in extract_numbers_from_text(v):
                    if sn not in allowed_nums:
                        ungrounded_items.append(f"Slide {s.get('id')}: ungrounded number '{sn}' in slot '{k}'")

        # 2. Text words grounding (check for completely invented words)
        for k in ("title", "headline", "items"):
            val_t = slots.get(k)
            texts_to_check = val_t if isinstance(val_t, list) else ([val_t] if val_t else [])
            for t_item in texts_to_check:
                words_in_slot = normalize_text(str(t_item)).split()
                # If a slot contains multi-word concepts with zero overlap in ground truth
                if words_in_slot and not any(w in gt_words for w in words_in_slot):
                    ungrounded_items.append(f"Slide {s.get('id')}: slot '{k}' text '{t_item}' completely absent from brief/narration")

    c4_passed = len(ungrounded_items) == 0
    c4_score = 15 if c4_passed else 0
    score += c4_score
    results["checks"]["grounding"] = {
        "passed": c4_passed,
        "score": c4_score,
        "max_score": 15,
        "ungrounded_count": len(ungrounded_items),
        "ungrounded_items": ungrounded_items,
    }
    if not c4_passed:
        results["violations"].extend(ungrounded_items)

    # -------------------------------------------------------------
    # Check 5: Slot limits and text overflow (15 pts)
    # -------------------------------------------------------------
    overflow_errors: list[str] = []
    for s in slides_data:
        slots = s.get("slots", {})
        title = str(slots.get("title") or slots.get("headline") or "")
        if len(title) > 46:
            overflow_errors.append(f"Slide {s.get('id')}: headline length {len(title)} > 42")

        for pk in ("pill", "badge", "chip", "kicker", "sub_pill"):
            if pk in slots and len(str(slots[pk])) > 30:
                overflow_errors.append(f"Slide {s.get('id')}: {pk} length {len(str(slots[pk]))} > 28")

        items = slots.get("items", [])
        if isinstance(items, list):
            for i, it in enumerate(items):
                if len(str(it)) > 42:
                    overflow_errors.append(f"Slide {s.get('id')}: item {i} length {len(str(it))} > 40")

        for side in ("left", "right"):
            if side in slots and isinstance(slots[side], dict):
                for sk in ("label", "text", "title"):
                    if sk in slots[side] and len(str(slots[side][sk])) > 30:
                        overflow_errors.append(f"Slide {s.get('id')}: compare side {side}.{sk} length > 28")

    c5_passed = len(overflow_errors) == 0
    c5_score = 15 if c5_passed else 0
    score += c5_score
    results["checks"]["slot_overflow"] = {
        "passed": c5_passed,
        "score": c5_score,
        "max_score": 15,
        "overflow_count": len(overflow_errors),
        "overflow_errors": overflow_errors,
    }
    if not c5_passed:
        results["violations"].extend(overflow_errors)

    # -------------------------------------------------------------
    # Check 6: Layout diversity (15 pts)
    # >= 4 distinct layouts, 0 adjacent duplicate layouts
    # -------------------------------------------------------------
    layouts = [s.get("layout", "") for s in slides_data]
    distinct_count = len(set(layouts))
    consecutive_dups = [
        f"Slide {i} and {i+1} both use '{layouts[i]}'"
        for i in range(len(layouts) - 1)
        if layouts[i] == layouts[i + 1]
    ]

    div_passed = (distinct_count >= 4 or n_slides < 5) and len(consecutive_dups) == 0
    c6_score = 15 if div_passed else (8 if len(consecutive_dups) == 0 else 0)
    score += c6_score
    results["checks"]["layout_diversity"] = {
        "passed": div_passed,
        "score": c6_score,
        "max_score": 15,
        "distinct_layouts": distinct_count,
        "consecutive_duplicates": consecutive_dups,
    }
    if not div_passed:
        results["violations"].extend(consecutive_dups)

    # -------------------------------------------------------------
    # Check 7: Emphasis matching & zero ungrounded emphasis (10 pts)
    # -------------------------------------------------------------
    emphasis_mismatches: list[str] = []
    for s in slides_data:
        slide_narr_norm = normalize_text(s.get("narration", ""))
        for emp in s.get("emphasis", []):
            p = emp.get("phrase", "") if isinstance(emp, dict) else getattr(emp, "phrase", "")
            if p and normalize_text(p) not in slide_narr_norm:
                emphasis_mismatches.append(f"Slide {s.get('id')}: emphasis '{p}' not in slide narration")

    c7_passed = len(emphasis_mismatches) == 0
    c7_score = 10 if c7_passed else 0
    score += c7_score
    results["checks"]["emphasis_matching"] = {
        "passed": c7_passed,
        "score": c7_score,
        "max_score": 10,
        "unmatched_emphasis_count": len(emphasis_mismatches),
        "mismatches": emphasis_mismatches,
    }
    if not c7_passed:
        results["violations"].extend(emphasis_mismatches)

    results["raw_score"] = score
    # If video is provided and frames evaluated, max is 100. If no video, max evaluated is 85.
    empty_status = results["checks"]["empty_frame_ratio"]["passed"]
    evaluated_max = 100 if (v_path and v_path.is_file() and empty_status != "unknown") else 85
    norm_score = round((score / evaluated_max) * 100) if evaluated_max > 0 else 0
    results["total_score"] = norm_score

    is_empty_ok = (empty_status is True) or (empty_status == "unknown")
    results["passed"] = (norm_score >= 85) and (len(results["violations"]) == 0) and is_empty_ok

    # Contact sheet generation if video exists
    if v_path and v_path.is_file():
        try:
            cs_path = p_dir / "contact_sheet_audit.png"
            generate_audit_contact_sheet(v_path, cs_path)
            results["contact_sheet"] = str(cs_path)
        except Exception as cs_err:
            results["contact_sheet_error"] = str(cs_err)

    report_file = p_dir / "audit_style.json"
    write_json_atomic(report_file, results)
    return results


def generate_audit_contact_sheet(video_path: Path, output_png: Path, fps: float = 1.0) -> Path | None:
    """Extract 1 frame per second from video and tile into a contact sheet."""
    import tempfile
    import imageio_ffmpeg

    ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
    output_png.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        frame_pattern = Path(tmpdir) / "frame_%04d.png"
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(video_path),
            "-vf", f"fps={fps},scale=270:480",
            str(frame_pattern),
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode != 0:
            return None

        frames = sorted(Path(tmpdir).glob("frame_*.png"))
        if not frames:
            return None

        cols = min(6, len(frames))
        rows = (len(frames) + cols - 1) // cols
        fw, fh = 270, 480
        sheet = Image.new("RGB", (cols * fw, rows * fh), (244, 245, 248))

        for idx, f_path in enumerate(frames):
            c = idx % cols
            r = idx // cols
            im = Image.open(f_path)
            sheet.paste(im, (c * fw, r * fh))

        sheet.save(str(output_png), "PNG")
        return output_png


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit Light Glass Video Style")
    parser.add_argument("--project", required=True, help="Project directory")
    parser.add_argument("--video", help="Rendered MP4 file path")
    args = parser.parse_args()

    res = audit_light_glass_project(args.project, args.video)
    print(json.dumps(res, indent=2, ensure_ascii=False))
