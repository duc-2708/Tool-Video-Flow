import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from schemas.edit_plan import EditPlan
from schemas.research_brief import ResearchBrief
from agents.visual_diversity import repair_numeric_cards
from utils.atomic_io import read_json_atomic, write_json_atomic

for p_name in ["auto-cong-nghe-3deb20b3", "auto-cong-nghe-efa8eac5"]:
    p_dir = ROOT / "output" / p_name
    plan_path = p_dir / "edit_plan.json"
    brief_path = p_dir / "brief.json"
    if plan_path.is_file() and brief_path.is_file():
        plan = EditPlan.model_validate(read_json_atomic(plan_path))
        brief = ResearchBrief.model_validate(read_json_atomic(brief_path))
        repair_numeric_cards(plan, brief)
        write_json_atomic(plan_path, plan.model_dump(mode="json"))
        print(f"Repaired {p_name}")
