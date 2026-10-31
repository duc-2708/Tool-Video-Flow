import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
from pathlib import Path

p = Path('output/auto-cong-nghe-b02014fc')
plan = json.loads((p / 'edit_plan.resolved.json').read_text(encoding='utf-8'))
sc1 = plan['scenes'][0]
print("vp:", sc1.get('visual_plan'))
