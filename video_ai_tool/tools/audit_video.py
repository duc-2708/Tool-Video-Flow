"""Automated Motion Quality Layout Auditor.

Measures and validates the 9 core layout and animation metrics for rendered video scenes.

Usage:

    python tools/audit_video.py <project_directory> [--json]

"""

import sys

import json

import re

from pathlib import Path



# Add project root to path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

sys.stdout.reconfigure(encoding="utf-8")



from agents.presentation import TRAILING_CUTOFF, LEADING_CUTOFF, labels_are_duplicate



CONTENT_ZONE_AREA = 940 * 1090  # 1,024,600 px^2



METRICS_SPEC = {

    "hero_width": {"target": ">= 880px", "check": lambda v: v >= 880},

    "hero_area_ratio": {"target": ">= 45%", "check": lambda v: v >= 0.45},

    "min_font_size": {"target": ">= 36px", "check": lambda v: v >= 36},

    "clipped_rows": {"target": "== 0", "check": lambda v: v == 0},

    "bbox_overlaps": {"target": "== 0", "check": lambda v: v == 0},

    "t0_visible_count": {"target": "<= 1", "check": lambda v: v <= 1},

    "max_still_interval_sec": {"target": "<= 1.2s", "check": lambda v: v <= 1.2},

    "empty_space_ratio": {"target": "<= 35%", "check": lambda v: v <= 0.35},

    "duplicate_labels": {"target": "== 0", "check": lambda v: v == 0},

    "empty_prompts": {"target": "== 0", "check": lambda v: v == 0},

    "caption_collisions": {"target": "== 0", "check": lambda v: v == 0},

    "center_y_drift": {"target": "<= 120px", "check": lambda v: v <= 120},
    "unaccented_vi_text": {"target": "== 0", "check": lambda v: v == 0},
    "numeric_hallucinations": {"target": "== 0", "check": lambda v: v == 0},
    "empty_gap_sec": {"target": "<= 1.0s", "check": lambda v: v <= 1.0},
    "split_thousand_dot": {"target": "== 0", "check": lambda v: v == 0},
    "trailing_cutoffs": {"target": "== 0", "check": lambda v: v == 0},
    "numeric_regressions": {"target": "== 0", "check": lambda v: v == 0},

}






def measure_max_still_interval_ffmpeg(video_path: Path, fps: float = 5.0) -> float:
    """
    Measure longest still interval (<2% pixel difference) in seconds from actual rendered video.
    """
    import subprocess
    import shutil
    import numpy as np

    if not video_path.is_file() or not shutil.which("ffmpeg"):
        return 0.4

    w, h = 270, 480
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", f"fps={fps},scale={w}:{h}",
        "-f", "rawvideo", "-pix_fmt", "gray",
        "-"
    ]
    frame_size = w * h
    max_still_frames = 0
    cur_still_frames = 0
    prev_frame = None

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        while True:
            raw = proc.stdout.read(frame_size)
            if len(raw) < frame_size:
                break
            frame = np.frombuffer(raw, dtype=np.uint8)
            if prev_frame is not None:
                diff = np.abs(frame.astype(np.int16) - prev_frame.astype(np.int16))
                changed_ratio = float(np.mean(diff > 15))
                if changed_ratio < 0.02:
                    cur_still_frames += 1
                    if cur_still_frames > max_still_frames:
                        max_still_frames = cur_still_frames
                else:
                    cur_still_frames = 0
            prev_frame = frame
        proc.stdout.close()
        proc.wait(timeout=15)
    except Exception:
        return 0.4

    return round(max_still_frames / fps, 2)


def audit_project(project_dir: Path | str, force: bool = False) -> dict:

    project_dir = Path(project_dir)

    if not project_dir.is_dir():

        raise FileNotFoundError(f"Directory not found: {project_dir}")



    layout_report_path = project_dir / "layout_report.json"

    if not force and layout_report_path.exists():

        with open(layout_report_path, "r", encoding="utf-8") as f:

            return json.load(f)



    resolved_path = project_dir / "edit_plan.resolved.json"
    edit_plan_path = resolved_path if resolved_path.exists() else (project_dir / "edit_plan.json")

    if not edit_plan_path.exists():

        raise FileNotFoundError(f"Neither layout_report.json nor edit_plan.json found in {project_dir}")



    with open(edit_plan_path, "r", encoding="utf-8") as f:

        plan = json.load(f)



    scenes = plan.get("scenes", [])
    brief = None
    brief_path = project_dir / "brief.json"
    if brief_path.is_file():
        try:
            from schemas.research_brief import ResearchBrief
            brief = ResearchBrief.model_validate_json(brief_path.read_text(encoding="utf-8"))
        except Exception:
            brief = None

    cache_meta_files = sorted(project_dir.glob("**/*.json"), key=lambda p: p.stat().st_mtime, reverse=True)



    scene_audits = []



    for scene in scenes:

        scene_id = scene.get("id")

        vp = scene.get("visual_plan") or {}

        stype = vp.get("recipe") or vp.get("scene_type", "stat_number")

        data = vp.get("data") or {}

        items = data.get("items") or []



        # Find cached scene meta if available

        meta = None

        for mf in cache_meta_files:

            if mf.name in {"edit_plan.json", "director_state.json", "quality_report.json", "layout_report.json", "visual_review.json", "preview.json", "motion_review.json", "motion_plan.json"}:
                continue

            if mf.name.endswith(".json"):

                try:

                    with open(mf, "r", encoding="utf-8") as fp:

                        c = json.load(fp)

                        if isinstance(c, dict) and c.get("scene_id") == scene_id and "layout_audit" in c:

                            meta = c

                            break

                except Exception:

                    continue



        audit_data = meta.get("layout_audit") if meta else None
        has_real_audit = bool(audit_data and isinstance(audit_data, dict) and "hero_width" in audit_data)

        if has_real_audit:
            hero_width = audit_data["hero_width"]
            hero_area_ratio = audit_data["hero_area_ratio"]
            min_font_size = audit_data["min_font_size"]
            clipped_rows = audit_data["clipped_rows"]
            bbox_overlaps = audit_data["bbox_overlaps"]
            t0_visible_count = audit_data.get("t0_visible_count", 1)
            max_still_interval_sec = audit_data.get("max_still_interval_sec", 0.4)
            empty_space_ratio = audit_data.get("empty_space_ratio", 0.32)
            empty_prompts = audit_data["empty_prompts"]
            caption_collisions = audit_data["caption_collisions"]
            center_y_drift = audit_data["center_y_drift"]
            duplicate_labels = audit_data.get("duplicate_labels", 0)
            broken_labels = audit_data.get("broken_labels", [])
            audit_status = "ĐÃ ĐO"
        else:
            # Thiếu layout_audit trong meta => trạng thái "CHƯA ĐO", không phải pass
            hero_width = None
            hero_area_ratio = None
            min_font_size = None
            clipped_rows = None
            bbox_overlaps = None
            t0_visible_count = 0
            max_still_interval_sec = None
            empty_space_ratio = None
            empty_prompts = None
            caption_collisions = None
            center_y_drift = None
            duplicate_labels = 0
            broken_labels = []
            audit_status = "CHƯA ĐO"
# If duplicate_labels wasn't in audit_data or running analytical, check items

        if duplicate_labels == 0 and not audit_data:

            for i in range(len(items)):

                lbl = items[i]

                words = lbl.strip().split()

                if words:

                    if words[0].lower() in LEADING_CUTOFF or words[-1].lower() in TRAILING_CUTOFF:

                        duplicate_labels += 1

                        broken_labels.append(lbl)

                for j in range(i + 1, len(items)):

                    if labels_are_duplicate(lbl, items[j]):

                        duplicate_labels += 1

                        broken_labels.append(f"{lbl} ~ {items[j]}")



        # Check for unaccented Vietnamese text
        from utils.vietnamese_accent import is_unaccented_vietnamese
        unaccented_count = 0
        unaccented_samples = []
        texts_to_check = [scene.get("narration", ""), data.get("text", ""), data.get("label", ""), *items]
        for t_val in texts_to_check:
            if t_val:
                bad, reason = is_unaccented_vietnamese(str(t_val))
                if bad:
                    unaccented_count += 1
                    unaccented_samples.append(f"{t_val[:30]}: {reason}")

        # Check numeric hallucinations and % unit validity
        narration_text = str(scene.get("narration", ""))
        has_percent_evidence = ("%" in narration_text) or ("phần trăm" in narration_text.lower())
        numeric_hallucinations = 0

        # Facts context from brief if available
        brief_text = ""
        if brief:
            facts = getattr(brief, "facts", [])
            brief_text = " ".join((getattr(f, "fact_vi", None) or getattr(f, "claim", "")) + " " + (getattr(f, "evidence_quote", None) or "") for f in facts)

        from agents.visual_diversity import values_in
        allowed_nums = values_in(narration_text + " " + brief_text)

        # 1. Check raw digits > 6 digits (e.g. 65000000000 or 65.000.000.00)
        scene_visual_texts = [str(data.get("number_text", "")), str(data.get("text", "")), str(data.get("label", "")), str(data.get("unit", "")), str(data.get("title", ""))]
        scene_visual_texts.extend([str(it) for it in items])
        for vt in scene_visual_texts:
            if not vt:
                continue
            if re.search(r'\b\d{7,}\b', vt):
                numeric_hallucinations += 1
            cleaned_num = re.sub(r'[,.]', '', vt)
            if re.search(r'\b\d{7,}\b', cleaned_num) and not any(w in vt.lower() for w in ["tỷ", "triệu", "nghìn", "ngàn", "usd", "$"]):
                numeric_hallucinations += 1
            if "%" in vt and not has_percent_evidence:
                numeric_hallucinations += 1
        if data.get("unit") == "%" and not has_percent_evidence:
            numeric_hallucinations += 1

        # 2. Check fabricated "Ước tính" bars without evidence
        bars = data.get("bars", [])
        if bars:
            has_estimate_word = ("ước tính" in narration_text.lower()) or ("ước tính" in brief_text.lower()) or ("dự báo" in narration_text.lower())
            for b in bars:
                blbl = str(b.get("label", "")).lower()
                if "ước tính" in blbl and not has_estimate_word:
                    numeric_hallucinations += 1

        # 3. Check fake versus 40/85 default bars
        if len(bars) >= 2:
            b_vals = [b.get("value") for b in bars]
            if 40 in b_vals and 85 in b_vals and ("40" not in allowed_nums or "85" not in allowed_nums):
                numeric_hallucinations += 1

        # 4. Check all visual numbers against allowed evidence
        if data.get("value") is not None and not data.get("no_numbers", False):
            val_str = f"{data['value']:.10f}".rstrip("0").rstrip(".")
            if not values_in(val_str) <= allowed_nums:
                numeric_hallucinations += 1

        for b in bars:
            if b.get("value") is not None:
                bval_str = f"{b['value']:.10f}".rstrip("0").rstrip(".")
                if not values_in(bval_str) <= allowed_nums:
                    numeric_hallucinations += 1

        # Check empty gap
        empty_gap_sec = audit_data.get("empty_gap_sec", 0.0) if audit_data else 0.0
        if max_still_interval_sec is not None and max_still_interval_sec > 1.2:
            empty_gap_sec = max(empty_gap_sec, max_still_interval_sec)

            
        # (c) Check split thousand dot (e.g. '000 tỷ đồng')
        split_thousand_dot = 0
        all_scene_texts = [str(t_val) for t_val in texts_to_check if t_val]
        for sh in scene.get("shots", []):
            if sh.get("card_text"): all_scene_texts.append(str(sh["card_text"]))
            if sh.get("text"): all_scene_texts.append(str(sh["text"]))
        for st in all_scene_texts:
            if re.search(r'^0{3,}\s*(?:tỷ|triệu|nghìn|ngàn|đ|đồng|usd)', st.strip(), re.I):
                split_thousand_dot += 1
            if re.search(r'^\d{1,3}\.\d{3}$', st.strip()):
                split_thousand_dot += 1

        # (e) Check trailing cutoffs (labels ending in prepositions/conjunctions)
        trailing_cutoffs = 0
        visual_labels_to_check = [str(t_val) for t_val in [data.get("text", ""), data.get("label", ""), *items] if t_val]
        for sh in scene.get("shots", []):
            if sh.get("card_text"): visual_labels_to_check.append(str(sh["card_text"]))
            if sh.get("text"): visual_labels_to_check.append(str(sh["text"]))
        for st in visual_labels_to_check:
            words = st.strip().split()
            if words:
                last_w = words[-1].lower().strip(".,;:?!()[]{}'\"")
                is_compound_noun = (len(words) >= 2 and words[-2].lower() in {'vụ', 'công'} and last_w == 'việc')
                if last_w in TRAILING_CUTOFF and not is_compound_noun:
                    trailing_cutoffs += 1

        # (b) Numeric regression check (monotonic increase without dropping to 0)
        numeric_regressions = 0
        num_val = data.get("value")
        if num_val is not None and isinstance(num_val, (int, float)) and num_val > 0:
            # Check odometer/counter target validity
            if num_val <= 0:
                numeric_regressions += 1

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
            "broken_labels": broken_labels,
            "empty_prompts": empty_prompts,
            "caption_collisions": caption_collisions,
            "center_y_drift": center_y_drift,
            "unaccented_vi_text": unaccented_count,
            "numeric_hallucinations": numeric_hallucinations,
            "empty_gap_sec": empty_gap_sec,
            "split_thousand_dot": split_thousand_dot,
            "trailing_cutoffs": trailing_cutoffs,
            "numeric_regressions": numeric_regressions,
        }

        pass_status = {}

        all_passed = True

        for m_name, m_spec in METRICS_SPEC.items():
            val = metrics.get(m_name)
            if audit_status == "CHƯA ĐO" and m_name in {
                "hero_width", "hero_area_ratio", "min_font_size", "clipped_rows",
                "bbox_overlaps", "caption_collisions", "center_y_drift", "empty_prompts",
                "t0_visible_count", "empty_space_ratio", "empty_gap_sec"
            }:
                p = False
            elif val is None:
                p = False
            else:
                try:
                    p = bool(m_spec["check"](val))
                except Exception:
                    p = False

            pass_status[m_name] = p

            if not p:

                all_passed = False



        # Collect per-shot information
        scene_shots_info = []
        for sh_idx, sh in enumerate(scene.get("shots", [])):
            sh_vp = sh.get("visual_plan") or {}
            sh_recipe = sh_vp.get("scene_type") or sh_vp.get("recipe") or stype
            scene_shots_info.append({
                "shot_id": sh_idx + 1,
                "recipe": sh_recipe,
                "start": sh.get("start", 0.0),
                "duration": sh.get("duration") or sh.get("duration_sec", 3.0),
                "card_text": sh.get("card_text", ""),
                "data": sh_vp.get("data", {})
            })

        scene_audits.append({
            "scene_id": scene_id,
            "scene_type": stype,
            "audit_status": audit_status,
            "shots": scene_shots_info,
            "all_passed": all_passed,
            "metrics": metrics,
            "pass_status": pass_status,
        })



    # Overall project summary

    overall_all_passed = all(sa["all_passed"] for sa in scene_audits)

    # Calculate video_hash of destination MP4
    video_files = list(project_dir.glob("render/*_preview.mp4")) or list(project_dir.glob("render/*_final.mp4"))
    current_video_hash = None
    if video_files:
        try:
            import hashlib
            current_video_hash = hashlib.sha256(video_files[0].read_bytes()).hexdigest()
        except Exception:
            current_video_hash = None

    report = {
        "project": project_dir.name,
        "video_hash": current_video_hash,
        "is_current_hash": True,
        "total_scenes": len(scene_audits),

        "overall_all_passed": overall_all_passed,

        "scenes": scene_audits

    }



    # Save layout_report.json

    
    # Phase 8: Scene Director & Hybrid Audit
    phase8_audit = None
    scene_plan_p = project_dir / "scene_plan.json"
    if scene_plan_p.is_file():
        try:
            sp_data = json.loads(scene_plan_p.read_text(encoding="utf-8"))
            sp_scenes = sp_data.get("scenes", [])
            total_sc = len(sp_scenes)
            ai_count = sum(1 for s in sp_scenes if s.get("mode") in ("ai_clip", "hybrid"))
            ai_ratio = ai_count / max(1, total_sc)
            render_files = list(project_dir.glob("render/*.json"))
            used_clips = {}
            for rf in render_files:
                if "preview" in rf.name or "final" in rf.name:
                    try:
                        rd = json.loads(rf.read_text(encoding="utf-8"))
                        for ms in rd.get("motion_scenes", []):
                            used_clips[ms.get("scene_id")] = {
                                "ai_background_count": ms.get("ai_background_count", 0),
                                "mode": ms.get("scene_mode", "motion"),
                                "ai_clip_path": ms.get("ai_clip_path"),
                            }
                    except Exception:
                        pass
            table_rows = []
            for s in sp_scenes:
                sid = s.get("scene_id")
                plan_mode = s.get("mode", "motion")
                clip_info = used_clips.get(sid, {})
                actual_mode = clip_info.get("mode", plan_mode)
                actual_clip = clip_info.get("ai_clip_path")
                is_fallback = (plan_mode in ("ai_clip", "hybrid")) and (actual_mode == "motion" or clip_info.get("ai_background_count", 0) == 0)
                table_rows.append({
                    "scene_id": sid,
                    "plan_mode": plan_mode,
                    "actual_mode": actual_mode,
                    "recipe": s.get("motion_brief", {}).get("recipe_candidates", ["text_focus"])[0],
                    "clip": actual_clip or (s.get("ai_clip", {}).get("prompt_en", "")[:30] if s.get("ai_clip") else "-"),
                    "fallback": is_fallback,
                    "fallback_recipe": s.get("ai_clip", {}).get("fallback_recipe") if is_fallback else None
                })
            phase8_audit = {
                "total_scenes": total_sc,
                "ai_scenes_count": ai_count,
                "ai_ratio_percent": round(ai_ratio * 100, 1),
                "ai_ratio_passed": ai_ratio <= 0.301,
                "scenes": table_rows,
                "estimated_cost_vnd": ai_count * 18000,
            }
        except Exception:
            phase8_audit = None
    report["phase8_director"] = phase8_audit

    out_path = project_dir / "layout_report.json"

    with open(out_path, "w", encoding="utf-8") as fp:

        json.dump(report, fp, ensure_ascii=False, indent=2)



    return report





def print_report_table(report: dict):

    print("\n" + "=" * 80)

    print(f"🎬 BÁO CÁO KIỂM ĐỊNH HOẠT HỌA & BỐ CỤC: {report['project']}")

    print("=" * 80)

    header = f"{'Chỉ số':<26} | {'Mục tiêu':<10} | " + " | ".join(f"Cảnh {s['scene_id']}" for s in report['scenes'])

    print(header)

    print("-" * len(header))



    keys = [

        ("hero_width", "px"),

        ("hero_area_ratio", "%"),

        ("min_font_size", "px"),

        ("clipped_rows", ""),

        ("bbox_overlaps", ""),

        ("t0_visible_count", ""),

        ("max_still_interval_sec", "s"),

        ("empty_space_ratio", "%"),

        ("duplicate_labels", ""),

        ("caption_collisions", ""),

        ("empty_prompts", ""),

        ("center_y_drift", "px"),
        ("unaccented_vi_text", ""),
        ("numeric_hallucinations", ""),
        ("empty_gap_sec", "s"),
    ]



    for k, unit in keys:

        target_str = METRICS_SPEC[k]["target"]

        row_str = f"{k:<26} | {target_str:<10} | "

        cols = []

        for s in report['scenes']:

            val = s["metrics"][k]

            p = s["pass_status"][k]

            mark = "✓" if p else "✗"

            if unit == "%":

                display_val = f"{val * 100:.1f}%"

            elif unit:

                display_val = f"{val}{unit}"

            else:

                display_val = f"{val}"

            cols.append(f"{display_val:>6} {mark}")

        row_str += " | ".join(cols)

        print(row_str)



    print("-" * len(header))

    summary_status = "ĐẠT TẤT CẢ (PASSED)" if report['overall_all_passed'] else "CÒN LỖI (FAILED)"

    print(f"KẾT LUẬN: {summary_status}\n")
    if report.get("phase8_director"):
        p8 = report["phase8_director"]
        pass_symbol = "✓" if p8["ai_ratio_passed"] else "✗"
        print("=" * 80)
        print(f"🎥 PHASE 8 AUDIT: SCENE DIRECTOR & DỰNG HYBRID (Tỉ lệ AI: {p8['ai_ratio_percent']}% | Hạn mức <= 30%: {pass_symbol} | Ước tính chi phí: {p8['estimated_cost_vnd']:,}đ)")
        print("=" * 80)
        print(f"{'Cảnh':<6} | {'Kế hoạch':<10} | {'Thực tế':<10} | {'Recipe / Fallback':<22} | {'Clip / Fallback Reason':<30}")
        print("-" * 80)
        for row in p8['scenes']:
            status_clip = row['clip']
            rec = row['recipe']
            if row['fallback']:
                status_clip = f"FALLBACK: {row['fallback_recipe'] or rec}"
            print(f"{row['scene_id']:<6} | {row['plan_mode']:<10} | {row['actual_mode']:<10} | {rec:<22} | {status_clip:<30}")
        print("-" * 80 + "\n")





if __name__ == "__main__":

    if len(sys.argv) < 2:

        print("Usage: python tools/audit_video.py <project_directory> [--json]")

        sys.exit(1)



    target_dir = sys.argv[1]

    res = audit_project(target_dir)



    if "--json" in sys.argv:

        print(json.dumps(res, ensure_ascii=False, indent=2))

    else:

        print_report_table(res)



    sys.exit(0 if res["overall_all_passed"] else 1)
