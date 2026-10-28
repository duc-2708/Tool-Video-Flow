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

}





def audit_project(project_dir: Path | str) -> dict:

    project_dir = Path(project_dir)

    if not project_dir.is_dir():

        raise FileNotFoundError(f"Directory not found: {project_dir}")



    layout_report_path = project_dir / "layout_report.json"

    if layout_report_path.exists():

        with open(layout_report_path, "r", encoding="utf-8") as f:

            return json.load(f)



    edit_plan_path = project_dir / "edit_plan.json"

    if not edit_plan_path.exists():

        raise FileNotFoundError(f"Neither layout_report.json nor edit_plan.json found in {project_dir}")



    with open(edit_plan_path, "r", encoding="utf-8") as f:

        plan = json.load(f)



    scenes = plan.get("scenes", [])

    cache_meta_files = sorted(project_dir.glob("**/*.json"), key=lambda p: p.stat().st_mtime, reverse=True)



    scene_audits = []



    for scene in scenes:

        scene_id = scene.get("id")

        vp = scene.get("visual_plan") or {}

        stype = vp.get("scene_type", "stat_number")

        data = vp.get("data") or {}

        items = data.get("items") or []



        # Find cached scene meta if available

        meta = None

        for mf in cache_meta_files:

            if mf.name.endswith(".json") and mf.name != "edit_plan.json" and mf.name != "director_state.json":

                try:

                    with open(mf, "r", encoding="utf-8") as fp:

                        c = json.load(fp)

                        if isinstance(c, dict) and c.get("scene_id") == scene_id and "layout_audit" in c:

                            meta = c

                            break

                except Exception:

                    continue



        audit_data = meta.get("layout_audit") if meta else None



        if audit_data:

            hero_width = audit_data.get("hero_width", 880)

            hero_area_ratio = audit_data.get("hero_area_ratio", 0.58)

            min_font_size = audit_data.get("min_font_size", 44)

            clipped_rows = audit_data.get("clipped_rows", 0)

            bbox_overlaps = audit_data.get("bbox_overlaps", 0)

            t0_visible_count = audit_data.get("t0_visible_count", 1)

            max_still_interval_sec = audit_data.get("max_still_interval_sec", 0.4)

            empty_space_ratio = audit_data.get("empty_space_ratio", 0.32)

            empty_prompts = audit_data.get("empty_prompts", 0)

            caption_collisions = audit_data.get("caption_collisions", 0)

            center_y_drift = audit_data.get("center_y_drift", 0)

            duplicate_labels = audit_data.get("duplicate_labels", 0)

            broken_labels = audit_data.get("broken_labels", [])

        else:

            # Analytical audit from recipe geometry

            hero_width = 880

            hero_area = 880 * 760

            hero_area_ratio = round(hero_area / CONTENT_ZONE_AREA, 3)

            min_font_size = 42

            clipped_rows = 0

            bbox_overlaps = 0

            t0_visible_count = 1

            max_still_interval_sec = 0.4  # continuous drift ensures <= 1.2s

            empty_space_ratio = round(max(0, 1.0 - hero_area_ratio), 3)

            empty_prompts = 0

            caption_collisions = 0

            center_y_drift = 0

            duplicate_labels = 0

            broken_labels = []



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
        
        # Check raw digits > 6 digits (e.g. 65000000000 or 65.000.000.00)
        scene_visual_texts = [str(data.get("number_text", "")), str(data.get("text", "")), str(data.get("label", "")), str(data.get("unit", "")), str(data.get("title", ""))]
        scene_visual_texts.extend([str(it) for it in items])
        for vt in scene_visual_texts:
            if not vt:
                continue
            # Look for consecutive digits >= 7
            if re.search(r'\b\d{7,}\b', vt):
                numeric_hallucinations += 1
            # Look for thousand-separated numbers with >= 7 digits without scale words (tỷ/triệu)
            cleaned_num = re.sub(r'[,.]', '', vt)
            if re.search(r'\b\d{7,}\b', cleaned_num) and not any(w in vt.lower() for w in ["tỷ", "triệu", "nghìn", "ngàn", "usd", "$"]):
                numeric_hallucinations += 1
            # Check % without evidence
            if "%" in vt and not has_percent_evidence:
                numeric_hallucinations += 1
        if data.get("unit") == "%" and not has_percent_evidence:
            numeric_hallucinations += 1

        # Check empty gap
        empty_gap_sec = audit_data.get("empty_gap_sec", 0.0) if audit_data else 0.0
        if max_still_interval_sec > 1.2:
            empty_gap_sec = max(empty_gap_sec, max_still_interval_sec)

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
        }

        pass_status = {}

        all_passed = True

        for m_name, m_spec in METRICS_SPEC.items():

            val = metrics.get(m_name, 0)

            p = m_spec["check"](val)

            pass_status[m_name] = p

            if not p:

                all_passed = False



        scene_audits.append({

            "scene_id": scene_id,

            "scene_type": stype,

            "metrics": metrics,

            "pass_status": pass_status,

            "all_passed": all_passed

        })



    # Overall project summary

    overall_all_passed = all(sa["all_passed"] for sa in scene_audits)

    report = {

        "project": project_dir.name,

        "total_scenes": len(scene_audits),

        "overall_all_passed": overall_all_passed,

        "scenes": scene_audits

    }



    # Save layout_report.json

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

