import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

p = ROOT / "output" / "auto-cong-nghe-d56d3ebe" / "edit_plan.json"
with open(p, "r", encoding="utf-8") as f:
    plan = json.load(f)

sc2 = plan["scenes"][1]
print("SCENE 2:")
print("Narration:", sc2.get("narration"))
print("Visual Plan:", json.dumps(sc2.get("visual_plan"), indent=2, ensure_ascii=False))
