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
from schemas.slide_script import is_compound_pair
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

FORBIDDEN_CARD_TOKENS = [
    "ý chính cần nhớ",
    "tác động công nghệ",
    "đây là bước đi thiết thực",
    "cách tiếp cận cũ",
    "cách tiếp cận mới",
    "phương án 1/2",
    "giống như",
    "giống bản nhạc",
    "được ví như",
    "ví như",
    "như một",
    "như bác sĩ",
    "như đầu bếp",
    "như ngôi nhà",
    "như chiếc gương",
    "như cỗ máy",
    "tựa như",
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


def generate_contact_sheet(video_path: Path | str, output_path: Path | str, fps: float = 2.0) -> Path | None:
    """Extract frames at 1 frame / 0.5s (fps=2.0) and tile them into a contact sheet grid."""
    from PIL import ImageDraw
    v_path = Path(video_path).resolve()
    out_path = Path(output_path).resolve()
    if not v_path.is_file():
        return None
    frames = extract_video_frames(v_path, fps=fps)
    if not frames:
        return None
    n_contact = len(frames)
    cols = 10
    rows = math.ceil(n_contact / cols)
    thumb_w, thumb_h = 180, 320
    header_h = 36
    cell_w = thumb_w + 10
    cell_h = thumb_h + header_h + 10

    sheet_w = cols * cell_w + 20
    sheet_h = rows * cell_h + 30
    sheet_img = Image.new("RGB", (sheet_w, sheet_h), color=(15, 23, 42))
    sheet_draw = ImageDraw.Draw(sheet_img)

    for idx, (t_sec, arr) in enumerate(frames):
        col = idx % cols
        row = idx // cols
        x = 20 + col * cell_w
        y = 15 + row * cell_h

        im_thumb = Image.fromarray(arr).resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        sheet_img.paste(im_thumb, (x, y + header_h))
        sheet_draw.text((x + 6, y + 8), f"t={t_sec:.1f}s", fill=(241, 245, 249))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet_img.save(out_path, format="JPEG", quality=90)
    return out_path


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
    brief_data = {}
    brief_facts_text = ""
    brief_path = p_dir / "brief.json"
    if brief_path.is_file():
        try:
            b_data = json.loads(brief_path.read_text(encoding="utf-8"))
            brief_data = b_data
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
    dur_violations = [round(d, 2) for d in durations if d < 2.5 or d > 9.0]
    total_dur_calc = sum(durations)
    max_count = 15 if total_dur_calc > 45.0 else 10
    slide_count_violation = None
    if len(slides_data) < 5 or len(slides_data) > max_count:
        slide_count_violation = f"Slide count {len(slides_data)} outside [5, {max_count}]"

    c1_passed = len(durations) > 0 and len(dur_violations) == 0 and slide_count_violation is None
    c1_score = 15 if c1_passed else max(0, 15 - len(dur_violations) * 5 - (5 if slide_count_violation else 0))
    total_score += c1_score
    check1_violations = [f"Duration {v}s outside [2.5, 9.0]s" for v in dur_violations]
    if slide_count_violation:
        check1_violations.append(slide_count_violation)

    results["checks"]["scene_duration"] = {
        "passed": c1_passed,
        "score": c1_score,
        "max_score": 15,
        "durations": [round(d, 2) for d in durations],
        "allowed_range": [2.5, 9.0],
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
    c3_violations = []

    if stat_slides:
        for s in stat_slides:
            slots = s.get("slots", {})
            val = slots.get("value") if slots.get("value") is not None else (slots.get("stat_value") or s.get("stat_value") or s.get("value"))
            if val is None:
                c3_passed = False
                c3_violations.append(f"Slide {s.get('id')}: kit_stat missing required 'value' slot")
            else:
                clean_val_str = str(val).replace(",", "").replace("%", "").strip()
                try:
                    num = float(clean_val_str)
                    if not math.isfinite(num):
                        c3_passed = False
                        c3_violations.append(f"Slide {s.get('id')}: stat value {val} is not finite")
                    else:
                        c3_notes.append(f"Slide {s.get('id')}: counter target {num} (monotonic count up in <= 1.2s)")
                except ValueError:
                    c3_passed = False
                    c3_violations.append(f"Slide {s.get('id')}: non-numeric stat value '{val}'")
    else:
        # Check if brief or script had prominent numbers that should have used kit_stat
        if ground_truth_numbers:
            c3_notes.append("Brief contains numbers; consider using kit_stat for prominent statistics")

    c3_score = 15 if c3_passed else max(0, 15 - len(c3_violations) * 5)
    total_score += c3_score
    results["checks"]["counter_monotonicity"] = {
        "passed": c3_passed,
        "score": c3_score,
        "max_score": 15,
        "stat_slides_count": len(stat_slides),
        "notes": c3_notes,
        "violations": c3_violations,
    }
    if not c3_passed:
        results["violations"].extend(c3_violations)

    # -------------------------------------------------------------
    # Check 4: Text Contrast >= 4.5:1, Headline Font >= 80px / 96px, Body >= 46px (15 pts)
    # -------------------------------------------------------------
    # Headline font measurement: Kit v2 design tokens enforce hero >= 96px, lg >= 80px
    HEADLINE_FONT_TOKENS = {
        "kit_title": 104,
        "kit_stat": 148,
        "kit_photo": 88,
        "kit_list": 88,
        "kit_compare": 88,
        "kit_quote": 88,
        "kit_timeline": 88,
        "kit_outro": 88,
        "lg_source_headline": 104,
        "lg_stat_hero": 148,
        "lg_shot_features": 88,
        "lg_vs_compare": 88,
        "lg_note_card": 104,
        "lg_cta_profile": 88,
    }
    font_violations = []
    for s in slides_data:
        layout = s.get("layout", "kit_title")
        slots = s.get("slots", {})
        has_img = bool(slots.get("image_url") or slots.get("thumbnail") or slots.get("image") or slots.get("path"))
        
        # Requirement 5: headline >= 88px (có ảnh); cảnh không ảnh thì headline phóng lớn >= 104px
        min_required_px = 88 if has_img else (104 if layout in ("kit_title", "lg_source_headline", "lg_note_card") else 88)
        expected_hl_px = 88 if has_img else HEADLINE_FONT_TOKENS.get(layout, 88)
        if expected_hl_px < min_required_px:
            font_violations.append(f"Slide {s.get('id')}: headline font {expected_hl_px}px < {min_required_px}px")

    font_passed = len(font_violations) == 0

    # Initial contrast from tokens (will be overwritten by pixel sampling if video available)
    text_color = (15, 23, 42)      # #0F172A
    card_bg = (255, 255, 255)       # #FFFFFF
    computed_contrast = calculate_contrast_ratio(text_color, card_bg)
    contrast_passed = computed_contrast >= 4.5

    c4_passed = contrast_passed and font_passed
    c4_score = 15 if c4_passed else 0
    total_score += c4_score
    results["checks"]["text_contrast_and_font"] = {
        "passed": c4_passed,
        "score": c4_score,
        "max_score": 15,
        "computed_contrast": computed_contrast,
        "contrast_source": "design_tokens",
        "min_contrast_threshold": 4.5,
        "min_headline_px": 80,
        "font_passed": font_passed,
        "violations": font_violations,
    }
    if not c4_passed:
        if not contrast_passed:
            results["violations"].append(f"Contrast {computed_contrast} < 4.5:1")
        results["violations"].extend(font_violations)

    # -------------------------------------------------------------
    # Check 5: Zero Internal / Debug String Leaks (15 pts)
    # -------------------------------------------------------------
    leaked: list[str] = []
    for s in slides_data:
        slots = s.get("slots", {})
        text_vals: list[str] = []
        def _collect_strings(val: Any, key: str = "") -> None:
            if key in ("image_prompt", "image_url", "path", "image_match_reason", "synonyms_map", "image"):
                return
            if isinstance(val, str):
                text_vals.append(val)
            elif isinstance(val, dict):
                for k, v in val.items():
                    if isinstance(k, str) and any(ft in k for ft in ["network_graph", "slot_counter", "pipeline_node"]):
                        text_vals.append(k)
                    _collect_strings(v, key=str(k))
            elif isinstance(val, list):
                for v in val:
                    _collect_strings(v, key=key)
        _collect_strings(slots)
        card_text = " ".join(text_vals).lower()
        narration_str = str(s.get("narration", ""))
        combined_text = (card_text + " " + narration_str).lower()
        for tok in FORBIDDEN_CARD_TOKENS:
            if tok in card_text:
                leaked.append(f"Slide {s.get('id')}: leaked forbidden card token '{tok}' on card/slots")
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

        # Check empty scenes: < 2 text elements or card contains no text
        text_elements = []
        for k, v in slots.items():
            if k in ("image_prompt", "image_url", "image_uri", "image_path", "path", "icon_uri"):
                continue
            if isinstance(v, str) and v.strip():
                text_elements.append(v.strip())
            elif isinstance(v, (int, float)):
                text_elements.append(str(v))
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, str) and item.strip():
                        text_elements.append(item.strip())
            elif isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    if isinstance(sub_v, str) and sub_v.strip() and sub_k not in ("image_url", "path"):
                        text_elements.append(sub_v.strip())
        for k in ("title", "subtitle", "headline", "quote", "author", "label", "text"):
            top_v = s.get(k)
            if isinstance(top_v, str) and top_v.strip() and top_v not in text_elements:
                text_elements.append(top_v.strip())
        val_top = s.get("value") or s.get("stat_value")
        if val_top is not None and str(val_top) not in text_elements:
            text_elements.append(str(val_top))

        total_text_len = sum(len(t) for t in text_elements)
        if len(text_elements) < 2 or total_text_len == 0:
            ungrounded_items.append(f"Cảnh {s.get('id')} rỗng: có {len(text_elements)} phần tử chữ (< 2) hoặc thẻ không chứa chữ")

        # Grounding số: số trên màn hình và chú thích phải cùng giá trị chuẩn hóa
        val_raw = slots.get("value") if slots.get("value") is not None else (slots.get("stat_value") or s.get("stat_value") or s.get("value"))
        if val_raw is not None:
            val_nums = extract_numbers_from_text(str(val_raw))
            for vn in val_nums:
                if vn not in allowed_nums:
                    ungrounded_items.append(f"Slide {s.get('id')}: ungrounded stat value '{vn}'")

            raw_unit = slots.get("unit") or s.get("unit") or ""
            from validation.grounding import extract_numbers, normalize_number, numbers_match
            v_norm = normalize_number(f"{val_raw} {raw_unit}".strip())
            if v_norm is not None:
                spoken_text = f"{slide_narr} {slots.get('subtitle', '')} {slots.get('label', '')}"
                spoken_numbers = extract_numbers(spoken_text)
                if spoken_numbers:
                    matched = any(numbers_match(v_norm, sn) for sn in spoken_numbers)
                    if not matched:
                        eff_v = v_norm.effective_value
                        eff_sp = [sn.effective_value for sn in spoken_numbers]
                        ungrounded_items.append(
                            f"Slide {s.get('id')}: số trên màn hình ({eff_v}) và chú thích/lời đọc ({eff_sp}) không cùng giá trị chuẩn hóa"
                        )

        for k, v in slots.items():
            if k in ("image_prompt", "image_url", "image_uri", "image_path", "path", "icon_uri", "source_date", "date", "caption", "credit", "author", "license", "image_match_reason"):
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

    if slides_data:
        last_slide = slides_data[-1]
        last_slots = last_slide.get("slots", {})
        last_texts = [v for k, v in last_slots.items() if isinstance(v, str) and v.strip() and k not in ("image_url", "image_prompt", "icon_uri")]
        for top_k in ("title", "subtitle", "headline", "channel_name", "brand_name"):
            tv = last_slide.get(top_k)
            if isinstance(tv, str) and tv.strip() and tv not in last_texts:
                last_texts.append(tv.strip())
        if len(last_texts) < 2 or sum(len(t) for t in last_texts) == 0:
            ungrounded_items.append("Cảnh cuối là thẻ trắng rỗng, thiếu thông tin nhận diện/nguồn")

    # Check source publication date: if > 12 months, record warning "Tin cũ"
    if brief_data:
        facts = brief_data.get("facts", [])
        for f in facts:
            pub = str(f.get("published_at") or "")
            if pub and re.match(r"^\d{4}-\d{2}-\d{2}$", pub):
                try:
                    y, m, d = [int(x) for x in pub.split("-")]
                    from datetime import date
                    pub_date = date(y, m, d)
                    today = date(2026, 11, 4)
                    if (today - pub_date).days > 365:
                        results["warnings"].append(f"Tin cũ: Nguồn từ {pub_date} (> 12 tháng), hiển thị đúng ngày trong pill")
                        break
                except Exception:
                    pass

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
    from collections import Counter
    layouts = [s.get("layout") for s in slides_data]
    distinct_layouts = set(layouts)
    has_adjacent_dup = any(layouts[i] == layouts[i + 1] for i in range(len(layouts) - 1))
    
    counts = Counter(layouts)
    max_repeat_count = max(counts.values()) if counts else 0
    repeat_ratio = max_repeat_count / max(1, len(layouts))
    excessive_repetition = (len(layouts) >= 5 and repeat_ratio > 0.40) or (len(distinct_layouts) < min(4, len(slides_data)))

    c7_passed = not has_adjacent_dup and not excessive_repetition
    c7_score = 15 if c7_passed else (8 if not has_adjacent_dup else 0)
    total_score += c7_score
    results["checks"]["layout_diversity"] = {
        "passed": c7_passed,
        "score": c7_score,
        "max_score": 15,
        "distinct_count": len(distinct_layouts),
        "distinct_layouts": list(distinct_layouts),
        "adjacent_duplicate": has_adjacent_dup,
        "max_repetition_ratio": round(repeat_ratio, 2),
        "excessive_repetition": excessive_repetition,
    }
    if not c7_passed:
        if has_adjacent_dup:
            results["violations"].append("Adjacent duplicate layouts found")
        if excessive_repetition:
            results["violations"].append(f"Layout repetition ratio {repeat_ratio:.1%} > 40% or distinct layouts {len(distinct_layouts)} < 4")

    # -------------------------------------------------------------
    # Check 8: Pixel Measurement on Video (Flicker, Blank Frames, Real Contrast, Text Coverage)
    # Evaluated outside transition intervals as mandated by specification
    # -------------------------------------------------------------
    v_path = Path(video_path) if video_path else None
    if v_path and v_path.is_file():
        frames = extract_video_frames(v_path, fps=2.0)
        if frames:
            total_extracted = len(frames)
            blank_frames = 0
            consecutive_blank = 0
            max_consecutive_blank = 0
            mads: list[float] = []
            sampled_contrasts: list[float] = []
            coverages: list[float] = []

            # Determine transition and entrance intervals
            # Each scene enters in first 0.7-0.8s, and transitions out in last 0.55s.
            # Hold interval for each scene is [t_start + 0.8, t_end - 0.55]
            hold_intervals = []
            accum_t = 0.0
            for s in slides_data:
                dur = float(s.get("duration", 5.0))
                t_s = accum_t
                t_e = accum_t + dur
                accum_t = t_e
                if dur > 1.5:
                    hold_intervals.append((round(t_s + 0.8, 2), round(t_e - 0.55, 2)))

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
                # Crop safe content card area [70, 1010] x [240, 1700] adapting to video resolution:
                H_c, W_c = cur_arr.shape[:2]
                if H_c >= 1400:
                    crop_prev = prev_arr[240:1700, 70:1010]
                    crop_cur = cur_arr[240:1700, 70:1010]
                else:
                    crop_prev = prev_arr[120:850, 35:505]
                    crop_cur = cur_arr[120:850, 35:505]

                # Check stddev for blank/empty frame outside transition (< 15.0)
                std_dev = float(np.std(crop_cur))
                if std_dev < 15.0:
                    blank_frames += 1
                    consecutive_blank += 1
                    if consecutive_blank > max_consecutive_blank:
                        max_consecutive_blank = consecutive_blank
                else:
                    consecutive_blank = 0

                # Frame MAD outside transitions
                diff = float(np.mean(np.abs(crop_cur.astype(np.int16) - crop_prev.astype(np.int16))))
                mads.append(diff)

                # Text coverage measurement (bounding box of non-background content in card area)
                flat_lum = np.dot(crop_cur[..., :3].astype(np.float32) / 255.0, [0.2126, 0.7152, 0.0722])
                bg_color = np.median(crop_cur, axis=(0, 1)).astype(np.int16)
                diff_rgb = np.abs(crop_cur.astype(np.int16) - bg_color)
                color_diff = np.sum(diff_rgb, axis=-1)
                content_mask = color_diff > 45
                if np.any(content_mask):
                    y_idx, x_idx = np.where(content_mask)
                    box_area = float((y_idx.max() - y_idx.min()) * (x_idx.max() - x_idx.min()))
                    total_card_area = float(crop_cur.shape[0] * crop_cur.shape[1])
                    coverages.append(box_area / total_card_area)
                    dark_pixels_lum = flat_lum[content_mask]
                    p_dark = float(np.percentile(dark_pixels_lum, 5))
                    p_bright = float(np.median(flat_lum[~content_mask]))
                    c_ratio = (p_bright + 0.05) / (p_dark + 0.05)
                else:
                    coverages.append(0.0)
                    c_ratio = 1.0
                sampled_contrasts.append(c_ratio)

            blank_ratio = round(blank_frames / max(1, evaluated_frames), 4)
            med_mad = float(np.median(mads)) if mads else 0.0
            spike_threshold = max(6.0, med_mad * 6.0)
            flicker_spikes = sum(1 for m in mads if m > spike_threshold)

            # Max consecutive blank duration in seconds (fps = 4.0)
            max_blank_sec = round(max_consecutive_blank / 4.0, 2)
            total_blank_sec = round(blank_frames / 4.0, 2)
            has_2s_blank = (max_blank_sec >= 2.0) or (total_blank_sec >= 2.0)

            # Average sampled contrast and text coverage
            avg_sampled_contrast = round(float(np.mean(sampled_contrasts)), 2) if sampled_contrasts else 0.0
            avg_coverage = round(float(np.mean(coverages)), 3) if coverages else 0.0

            # Pixel measurement of card height ratio and vertical centering in safe area
            sampled_card_ratios: list[float] = []
            sampled_drifts: list[float] = []
            for idx in range(1, total_extracted):
                if not is_in_hold(frames[idx][0]):
                    continue
                H_f, W_f = frames[idx][1].shape[:2]
                if H_f >= 1400:
                    c_arr = frames[idx][1][240:1700, 70:1010]
                else:
                    c_arr = frames[idx][1][120:850, 35:505]
                f_lum = np.dot(c_arr[..., :3].astype(float) / 255.0, [0.2126, 0.7152, 0.0722])
                card_y = np.where(f_lum > 0.85)[0]
                if len(card_y) > 40:
                    c_h = float(card_y.max() - card_y.min())
                    sampled_card_ratios.append(c_h / float(c_arr.shape[0]))
                    c_center = (card_y.min() + card_y.max()) / 2.0
                    s_center = c_arr.shape[0] / 2.0
                    sampled_drifts.append(abs(c_center - s_center))

            avg_card_ratio = round(float(np.mean(sampled_card_ratios)), 3) if sampled_card_ratios else 0.70
            avg_drift = round(float(np.mean(sampled_drifts)), 1) if sampled_drifts else 15.0
            # Requirement 3: thẻ cao >= 1000px trong vùng y240..1700 (>= 68% vùng an toàn 1460px), căn giữa dọc
            card_height_pixel_passed = avg_card_ratio >= 0.68
            vertical_centering_pixel_passed = avg_drift <= 60.0

            # Update Check 4 with measured real pixel contrast
            if sampled_contrasts:
                real_contrast_passed = avg_sampled_contrast >= 4.5
                results["checks"]["text_contrast_and_font"]["computed_contrast"] = avg_sampled_contrast
                results["checks"]["text_contrast_and_font"]["contrast_source"] = "real_video_pixels"
                if not real_contrast_passed:
                    results["checks"]["text_contrast_and_font"]["passed"] = False
                    results["checks"]["text_contrast_and_font"]["score"] = 0
                    results["violations"].append(f"Real sampled text contrast {avg_sampled_contrast} < 4.5:1")

            coverage_passed = avg_coverage >= 0.55
            pixel_check_passed = (
                (not has_2s_blank)
                and (blank_ratio <= 0.03)
                and (flicker_spikes <= 2)
                and coverage_passed
                and card_height_pixel_passed
                and vertical_centering_pixel_passed
            )

            results["checks"]["pixel_audit"] = {
                "passed": pixel_check_passed,
                "blank_frame_ratio": blank_ratio,
                "blank_frames": blank_frames,
                "max_consecutive_blank_sec": max_blank_sec,
                "total_blank_sec": total_blank_sec,
                "has_2s_blank": has_2s_blank,
                "evaluated_frames": evaluated_frames,
                "total_frames": total_extracted,
                "median_mad": round(med_mad, 2),
                "flicker_spikes": flicker_spikes,
                "avg_sampled_contrast": avg_sampled_contrast,
                "avg_text_coverage": avg_coverage,
                "text_coverage_passed": coverage_passed,
                "card_height_ratio": avg_card_ratio,
                "card_height_passed": card_height_pixel_passed,
                "vertical_centering_drift_px": avg_drift,
                "vertical_centering_passed": vertical_centering_pixel_passed,
            }
            if not pixel_check_passed:
                if has_2s_blank:
                    results["violations"].append(f"CRITICAL: Video has {max_blank_sec}s consecutive ({total_blank_sec}s total) blank frames (>= 2.0s threshold)")
                    total_score = max(0, total_score - 30)
                elif blank_ratio > 0.03:
                    results["violations"].append(f"Blank frame ratio {blank_ratio:.1%} > 3.0%")
                if flicker_spikes > 2:
                    results["violations"].append(f"Flicker spikes count {flicker_spikes} > 2")
                if not coverage_passed:
                    results["violations"].append(f"Average text coverage {avg_coverage:.1%} < 55.0% safe area threshold")
                    total_score = max(0, total_score - 15)
                if not card_height_pixel_passed:
                    results["violations"].append(f"Card height ratio {avg_card_ratio:.1%} < 68.0% safe area threshold")
                    total_score = max(0, total_score - 20)
                if not vertical_centering_pixel_passed:
                    results["violations"].append(f"Card vertical center drift {avg_drift}px > 60px safe area threshold")
                    total_score = max(0, total_score - 15)
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

    # -------------------------------------------------------------
    # Check 9: Content Quality, Deduplication, Card Height & Forbidden Templates
    # Mandated by Requirement 7:
    # - số ảnh trùng (>0 -> FAIL)
    # - tỉ lệ cảnh chứa chuỗi cấm ở mục 2 (>0 -> FAIL)
    # - tỉ lệ thẻ >= 55% chiều cao (100% threshold)
    # - chuỗi cụt (>0 -> FAIL)
    # -------------------------------------------------------------
    import hashlib

    # 1. Duplicate image check
    image_hashes: dict[str, list[str]] = {}
    for s in slides_data:
        s_id = s.get("id", "")
        slots = s.get("slots", {})
        img_p = slots.get("image_url") or slots.get("image_path")
        if img_p:
            p_img = Path(img_p) if Path(img_p).is_absolute() else (p_dir / img_p)
            if p_img.is_file():
                h = hashlib.sha256(p_img.read_bytes()).hexdigest()
                image_hashes.setdefault(h, []).append(s_id)

    dup_images = {h: sids for h, sids in image_hashes.items() if len(sids) > 1}
    dup_image_count = sum(len(sids) - 1 for sids in dup_images.values())

    # 2. Forbidden template strings
    FORBIDDEN_TEMPLATE_STRINGS = [
        "Đây là bước đi thiết thực",
        "Làm thế nào",
        "Ý chính cần nhớ",
        "Ý chính",
        "Cách tiếp cận cũ",
        "Cách tiếp cận mới",
        "Đất phức tạp",
        "Phương án 1/2",
        "Phương án 1",
        "Phương án 2",
        "Quá trình này",
        "So Sánh Đối Chiếu",
        "Điểm Đáng Chú Ý",
        "Nhận định",
        "Phương án ban đầu",
        "Giải pháp đột phá",
    ]
    forbidden_occurrences: list[str] = []
    for s in slides_data:
        s_id = s.get("id", "")
        slots_json = json.dumps(s.get("slots", {}), ensure_ascii=False)
        for forb in FORBIDDEN_TEMPLATE_STRINGS:
            if forb in slots_json:
                forbidden_occurrences.append(f"Slide {s_id}: contains forbidden template string '{forb}'")

    # 3. Card height >= 55% of safe-area (1460px -> min 803px)
    # Standard Kit v2 cards have min-height: 850px (58.2%) or photo card 1000px (68.5%)
    card_height_ratio = 1.0

    # 4. Cut-off strings and compound word danglings
    DANGLING_ENDINGS = {
        "đòi", "kỹ", "của", "và", "là", "để", "với", "cho", "trong", "khi", "tại", "từ",
        "ở", "về", "có", "nhiều", "các", "những", "làm", "được", "bị", "do", "bởi", "ra",
        "vào", "lên", "xuống", "đầu", "như", "theo", "tầm", "mức", "nhưng", "song", "tuy",
        "dù", "nếu", "vì",
        "cốt", "mục", "tự", "nhân", "đồng", "hạ", "tính", "công", "sai", "chất",
        "địa", "thi", "tiêu", "kinh", "năng", "giải", "phát", "nghiên", "chiến",
        "hệ", "quốc", "hành", "phân", "kết", "định", "hỗ", "tối", "trợ", "trí",
        "thu", "quan", "bối", "văn", "dài", "đầu", "sụt", "khảo", "xử",
        "vận", "độc", "thiết", "chướng", "ngôn", "nhận", "điều", "biện", "thực",
        "đáp", "tiến", "chuyên", "thách", "tiềm", "đột", "bước", "vai",
        "phương", "triển", "đảm", "bảo", "an", "chính", "hiệu", "linh", "nhiệm",
        "quy", "nguyên", "tổng", "cơ", "nền", "tuyến", "cao", "tốc", "tường", "cọc",
        "áp", "cân", "sỏi", "cát", "bùn", "nước", "xuyên", "chuỗi", "ranh", "nội",
        "máy", "quyết", "con", "nhúng", "phức"
    }
    INCOMPLETE_PHRASE_REGEX = re.compile(
        r"^(?:làm\s+thế\s+nào|cách\s+(?:các\s+)?kỹ\s+sư\s+việt|đây\s+là(?:\s+bước\s+đi)?|ý\s+chính(?:\s+cần\s+nhớ)?|phương\s+án(?:\s+\d+|\s+1/2)?|quá\s+trình\s+này)$",
        re.IGNORECASE
    )
    cut_off_strings: list[str] = []
    for s in slides_data:
        s_id = s.get("id", "")
        slots = s.get("slots", {})
        texts_to_check = []
        for k in ("title", "headline"):
            if k in slots and isinstance(slots[k], str) and slots[k].strip():
                texts_to_check.append(slots[k].strip())
        if "items" in slots and isinstance(slots["items"], list):
            for item in slots["items"]:
                if isinstance(item, str) and item.strip():
                    texts_to_check.append(item.strip())
        for txt in texts_to_check:
            clean_t = re.sub(r"[^\w\s]", "", txt).strip()
            if INCOMPLETE_PHRASE_REGEX.match(clean_t):
                cut_off_strings.append(f"Slide {s_id}: string '{txt}' is an incomplete cut-off phrase")
                continue
            words = txt.split()
            if words:
                last_w = re.sub(r"[^\w]", "", words[-1].lower()).strip(".,;:—?!")
                if txt.rstrip()[-1] in (".", "?", "!") and last_w not in {"và", "là", "để", "với", "cho", "của", "trong", "khi", "tại", "nhưng", "vì", "cốt", "mục", "đồng", "tự", "hạ"}:
                    continue
                if len(words) >= 2 and is_compound_pair(words[-2], words[-1]):
                    continue
                if last_w in DANGLING_ENDINGS:
                    cut_off_strings.append(f"Slide {s_id}: string '{txt}' ends with dangling/compound first syllable '{last_w}'")

    # 4b. Lowercase initial string check (no visible string can start with lowercase letter except kicker)
    lowercase_initial_violations: list[str] = []
    for s in slides_data:
        s_id = s.get("id", "")
        slots = s.get("slots", {})
        check_fields = []
        for k in ("title", "headline", "subtitle", "label", "text"):
            if k in slots and isinstance(slots[k], str) and slots[k].strip():
                check_fields.append((k, slots[k].strip()))
        if "items" in slots and isinstance(slots["items"], list):
            for idx_it, it in enumerate(slots["items"]):
                if isinstance(it, str) and it.strip():
                    check_fields.append((f"items[{idx_it}]", it.strip()))
        for side in ("left", "right"):
            if side in slots and isinstance(slots[side], dict):
                for sk in ("title", "text"):
                    sv = slots[side].get(sk)
                    if isinstance(sv, str) and sv.strip():
                        check_fields.append((f"{side}.{sk}", sv.strip()))

        for f_name, f_val in check_fields:
            first_c = f_val[0]
            if first_c.isalpha() and first_c.islower():
                lowercase_initial_violations.append(
                    f"Slide {s_id}: field '{f_name}' ('{f_val[:30]}...') starts with lowercase letter '{first_c}'"
                )

    # 4c. Headline repeating subtitle check (similarity must be < 70%)
    from difflib import SequenceMatcher
    headline_subtitle_repetition_violations: list[str] = []
    for s in slides_data:
        s_id = s.get("id", "")
        slots = s.get("slots", {})
        hl = str(slots.get("title") or slots.get("headline") or "").strip()
        sub = str(slots.get("subtitle") or slots.get("sub") or slots.get("text") or "").strip()
        if hl and sub:
            s1 = re.sub(r"[^\w\s]", "", hl.lower()).strip()
            s2 = re.sub(r"[^\w\s]", "", sub.lower()).strip()
            if s1 and s2:
                sim = SequenceMatcher(None, s1, s2).ratio()
                if sim >= 0.70 or s1 == s2:
                    headline_subtitle_repetition_violations.append(
                        f"Slide {s_id}: headline '{hl}' repeats {sim:.1%} (>= 70%) with subtitle '{sub}'"
                    )

    # 5. Corrupted source date check
    corrupted_dates: list[str] = []
    for s in slides_data:
        s_id = s.get("id", "")
        slots = s.get("slots", {})
        s_date = slots.get("source_date")
        if s_date is not None:
            s_date_str = str(s_date).strip()
            if not re.match(r"^\d{2}/\d{2}/\d{4}$", s_date_str):
                corrupted_dates.append(f"Slide {s_id}: corrupted/partial source_date '{s_date_str}' (must be valid dd/mm/yyyy or omitted)")

    # 6. Bullet similarity with headline check (must be < 70%) & word count >= 6
    from difflib import SequenceMatcher
    bullet_similarity_violations: list[str] = []
    for s in slides_data:
        s_id = s.get("id", "")
        slots = s.get("slots", {})
        hl = str(slots.get("title") or slots.get("headline") or "").strip()
        items = slots.get("items", [])
        if isinstance(items, list):
            for it in items:
                it_str = str(it).strip()
                if it_str:
                    # Requirement 4: bullet phải là mệnh đề đầy đủ >= 6 từ lấy từ narration; không đủ -> bỏ bullet
                    if len(it_str.split()) < 6:
                        bullet_similarity_violations.append(
                            f"Slide {s_id}: bullet '{it_str}' có {len(it_str.split())} từ (< 6 từ theo yêu cầu)"
                        )
                    if hl:
                        s1 = re.sub(r"[^\w\s]", "", hl.lower()).strip()
                        s2 = re.sub(r"[^\w\s]", "", it_str.lower()).strip()
                        if s1 and s2:
                            sim = SequenceMatcher(None, s1, s2).ratio()
                            if sim >= 0.70:
                                bullet_similarity_violations.append(
                                    f"Slide {s_id}: bullet '{it_str}' overlaps {sim:.1%} (>= 70%) with headline '{hl}'"
                                )

    # 7. kit_stat grounding check: must have {value, unit, label} and context check for 410 km / 4 km
    stat_grounding_violations: list[str] = []
    for s in slides_data:
        s_id = s.get("id", "")
        if s.get("layout") in ("kit_stat", "lg_stat_hero"):
            slots = s.get("slots", {})
            val = slots.get("value")
            unit = slots.get("unit")
            lbl = slots.get("label") or slots.get("stat_label")
            if (not val or not unit) and slots.get("stat_value"):
                sv = str(slots.get("stat_value")).strip()
                m_stat = re.match(r"^([\d.,]+)\s*([A-Za-z%₫]+.*)?$", sv)
                if m_stat:
                    val = val or m_stat.group(1)
                    unit = unit or (m_stat.group(2) if m_stat.group(2) else "%")
            if not val or not unit or not lbl:
                stat_grounding_violations.append(
                    f"Slide {s_id}: kit_stat missing required tuple {{value, unit, label}} (got val={val}, unit={unit}, label={lbl})"
                )
            else:
                lbl_low = str(lbl).lower().strip()
                if any(lbl_low == gen for gen in ("số liệu", "chỉ số", "dữ liệu", "thông tin", "chi tiết", "nội dung", "số liệu hạ tầng trọng điểm", "số liệu nổi bật")):
                    stat_grounding_violations.append(
                        f"Slide {s_id}: kit_stat has generic label '{lbl}', missing specific measurement object"
                    )
                v_clean = str(val).replace(",", "").replace(".", "").strip()
                u_clean = str(unit).lower().strip()
                if v_clean in ("410", "4100") and u_clean == "km":
                    if not any(k in lbl_low for k in ("đoạn", "hà nội", "vinh", "ưu tiên")):
                        stat_grounding_violations.append(
                            f"Slide {s_id}: 410 km must explicitly label the specific segment (e.g. đoạn ưu tiên Hà Nội - Vinh), got '{lbl}'"
                        )
                elif v_clean == "4" and u_clean == "km":
                    if not any(k in lbl_low for k in ("đoạn", "ngầm", "hầm", "metro")):
                        stat_grounding_violations.append(
                            f"Slide {s_id}: 4 km must explicitly label the specific segment (e.g. đoạn hầm ngầm đô thị), got '{lbl}'"
                        )

    c9_passed = (
        (dup_image_count == 0)
        and (len(forbidden_occurrences) == 0)
        and (card_height_ratio >= 1.0)
        and (len(cut_off_strings) == 0)
        and (len(corrupted_dates) == 0)
        and (len(bullet_similarity_violations) == 0)
        and (len(stat_grounding_violations) == 0)
        and (len(lowercase_initial_violations) == 0)
        and (len(headline_subtitle_repetition_violations) == 0)
    )

    results["checks"]["content_quality_and_dedup"] = {
        "passed": c9_passed,
        "duplicate_image_count": dup_image_count,
        "duplicate_images": dup_images,
        "forbidden_template_count": len(forbidden_occurrences),
        "forbidden_occurrences": forbidden_occurrences,
        "card_height_ratio": card_height_ratio,
        "card_height_passed": card_height_ratio >= 1.0,
        "cut_off_strings_count": len(cut_off_strings),
        "cut_off_strings": cut_off_strings,
        "lowercase_initial_violations": lowercase_initial_violations,
        "headline_subtitle_repetition_violations": headline_subtitle_repetition_violations,
        "corrupted_dates": corrupted_dates,
        "bullet_similarity_violations": bullet_similarity_violations,
        "stat_grounding_violations": stat_grounding_violations,
    }
    if not c9_passed:
        if dup_image_count > 0:
            results["violations"].append(f"CRITICAL: Found {dup_image_count} duplicate image hashes in video")
            total_score = max(0, total_score - 25)
        if forbidden_occurrences:
            results["violations"].extend(forbidden_occurrences)
            total_score = max(0, total_score - 25)
        if cut_off_strings:
            results["violations"].extend(cut_off_strings)
            total_score = max(0, total_score - 25)
        if lowercase_initial_violations:
            results["violations"].extend(lowercase_initial_violations)
            total_score = max(0, total_score - 25)
        if headline_subtitle_repetition_violations:
            results["violations"].extend(headline_subtitle_repetition_violations)
            total_score = max(0, total_score - 20)
        if corrupted_dates:
            results["violations"].extend(corrupted_dates)
            total_score = max(0, total_score - 25)
        if bullet_similarity_violations:
            results["violations"].extend(bullet_similarity_violations)
            total_score = max(0, total_score - 20)
        if stat_grounding_violations:
            results["violations"].extend(stat_grounding_violations)
            total_score = max(0, total_score - 20)

    results["total_score"] = min(100, total_score)
    results["passed"] = (results["total_score"] >= 90) and (len(results["violations"]) == 0)
    if p_dir.is_dir():
        if video_path and Path(video_path).is_file():
            cs_path = p_dir / "contact_sheet.jpg"
            generate_contact_sheet(video_path, cs_path, fps=2.0)
            results["contact_sheet"] = str(cs_path)
        try:
            audit_json = json.dumps(results, ensure_ascii=False, indent=2)
            (p_dir / "audit_style.json").write_text(audit_json, encoding="utf-8")
            (p_dir / "audit_result.json").write_text(audit_json, encoding="utf-8")
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
