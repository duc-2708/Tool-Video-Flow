import json
from pathlib import Path
from agents.illustrations import enough
from schemas.edit_plan import EditPlan
from schemas.assets import ResolvedEditPlan

p = Path("output/auto-tin-tuc-393af953")
ep_data = json.loads((p / "edit_plan.json").read_text(encoding="utf-8"))
ep = EditPlan.model_validate(ep_data)

epr_data = json.loads((p / "edit_plan.resolved.json").read_text(encoding="utf-8"))
epr = ResolvedEditPlan.model_validate(epr_data)

vp_data = json.loads((p / "visual_plan.json").read_text(encoding="utf-8"))

print(f"Total scenes: {len(ep.scenes)}")
for sc in ep.scenes:
    vp = sc.visual_plan
    vp_json_sc = next((s for s in vp_data.get("scenes", []) if s.get("scene_id") == sc.id), None)
    recipe = vp.scene_type if vp else None
    
    # check enough()
    is_enough = enough(vp.scene_type, vp.data) if vp else False
    
    # check annotations
    annots = vp.annotations if vp else []
    
    print(f"--- SCENE {sc.id} ---")
    print(f"  visual_plan exists: {vp is not None}")
    print(f"  scene_type: {vp.scene_type if vp else None}")
    print(f"  motion_recipe: {vp.motion_recipe if vp else None}")
    print(f"  recipe in vp.json: {vp_json_sc.get('recipe') if vp_json_sc else None}")
    print(f"  data: {vp.data if vp else None}")
    print(f"  enough(): {is_enough}")
    print(f"  annotations count: {len(annots)}")
    print(f"  annotations: {annots}")
    print(f"  shots count: {len(sc.shots)}")
    for i, sh in enumerate(sc.shots):
        print(f"    Shot {i+1}: type={sh.type}, card_text={sh.card_text}, visual={sh.visual.template if sh.visual else None}")
