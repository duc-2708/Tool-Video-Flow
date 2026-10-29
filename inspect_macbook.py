import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

p = Path("video_ai_tool/output/auto-cong-nghe-d56d3ebe/edit_plan.json")
data = json.loads(p.read_text(encoding="utf-8"))
print("Title:", data.get("title"))
for s in data.get("scenes", []):
    vp = s.get("visual_plan") or {}
    print(f"Scene {s.get('id')}:")
    print("  Narration:", s.get("narration")[:60])
    print("  VisualPlan scene_type:", vp.get("scene_type"))
    d = vp.get("data") or {}
    print("  Data text/value/unit/number_text:", d.get("text"), d.get("value"), d.get("unit"), d.get("number_text"))
    if d.get("bars"):
        print("  Bars:", [(b.get("label"), b.get("value"), b.get("unit")) for b in d.get("bars")])
