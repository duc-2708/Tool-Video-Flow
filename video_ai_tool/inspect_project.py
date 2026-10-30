import json
from pathlib import Path

p = Path("output/auto-tin-tuc-393af953")

def load(name):
    f = p / name
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return None

vp = load("visual_plan.json")
ep = load("edit_plan.json")
epr = load("edit_plan.resolved.json")
qr = load("quality_report.json")
lr = load("layout_report.json")
mp = load("render/motion_plan.json")
vr = load("render/visual_review.json")
mr = load("render/motion_review.json")
final = load("render/final.json")
run_state = load("run_state.json")

print("=== RUN STATE ===")
if run_state:
    print("stages:", list(run_state.get("stages", {}).keys()))
    for st, v in run_state.get("stages", {}).items():
        print(f"  {st}: {v.get('status')}")

print("\n=== VISUAL_PLAN.JSON ===")
if vp:
    for sc in vp.get("scenes", []):
        el_types = [e.get("type") for e in sc.get("elements", [])]
        print(f"Scene {sc.get('scene_id')}: recipe={sc.get('recipe')}, layout={sc.get('layout')}, elements={el_types}")
else:
    print("None")

print("\n=== EDIT_PLAN.JSON SCENES ===")
if ep:
    for sc in ep.get("scenes", []):
        v = sc.get("visual_plan")
        st = v.get("scene_type") if v else None
        rc = v.get("motion_recipe") if v else None
        shots = [s.get("type") for s in sc.get("shots", [])]
        print(f"Scene {sc.get('id')}: visual_plan={bool(v)}, scene_type={st}, recipe={rc}, shots={shots}")

print("\n=== EDIT_PLAN.RESOLVED.JSON SCENES ===")
if epr:
    for sc in epr.get("scenes", []):
        v = sc.get("visual_plan")
        st = v.get("scene_type") if v else None
        rc = v.get("motion_recipe") if v else None
        shots = [s.get("type") for s in sc.get("shots", [])]
        print(f"Scene {sc.get('id')}: visual_plan={bool(v)}, scene_type={st}, recipe={rc}, shots={shots}")

print("\n=== MOTION_PLAN.JSON (in render/) ===")
if mp:
    for sc in mp.get("scenes", []):
        v = sc.get("visual_plan")
        st = v.get("scene_type") if v else None
        rc = v.get("motion_recipe") if v else None
        shot_vis = [s.get("visual", {}).get("template") for s in sc.get("shots", [])]
        print(f"Scene {sc.get('id')}: visual_plan scene_type={st}, recipe={rc}, shot templates={shot_vis}")

print("\n=== QUALITY REPORT ===")
if qr:
    for k, v in qr.items():
        if k not in ["scenes"]:
            print(f"  {k}: {v}")

print("\n=== LAYOUT REPORT ===")
if lr:
    for sc in lr.get("scenes", []):
        print(f"Scene {sc.get('scene_id')}: recipe={sc.get('recipe')}, passed={sc.get('passed')}, violations={sc.get('violations')}")

print("\n=== VISUAL REVIEW ===")
if vr:
    print("overall_passed:", vr.get("overall_passed"))
    for sc in vr.get("scenes", []):
        print(f"Scene {sc.get('scene_id')}: template={sc.get('template')}, recipe={sc.get('recipe')}, fallback={sc.get('fallback')}, notes={sc.get('notes')}")

print("\n=== MOTION REVIEW ===")
if mr:
    print("motion_review:", mr)
