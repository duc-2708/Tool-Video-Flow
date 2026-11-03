import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[1]
ss = json.load(open(ROOT / "output/auto-cong-nghe-f4d9a86b/slide_script.json", encoding="utf-8"))
for i, s in enumerate(ss["slides"]):
    print(f"Beat {i+1:02d} ({s['id']}): {s['narration']}")
