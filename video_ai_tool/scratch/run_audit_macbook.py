import sys
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.audit_video import audit_project

project_dir = ROOT / "output" / "auto-cong-nghe-d56d3ebe"
res = audit_project(project_dir, force=True)

print("overall_all_passed:", res.get("overall_all_passed"))
for sc in res.get("scenes", []):
    sid = sc["scene_id"]
    stype = sc["scene_type"]
    passed = sc["all_passed"]
    print(f"Scene {sid} ({stype}): passed={passed}")
    if not passed:
        fails = {k: sc["metrics"].get(k) for k, v in sc["pass_status"].items() if not v}
        print("   FAILS:", fails)
