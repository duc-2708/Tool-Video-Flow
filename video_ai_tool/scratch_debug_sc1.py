import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
from pathlib import Path

p = Path('output/auto-cong-nghe-b02014fc/render/motion_cache')
for f in sorted(p.glob('*.json'), key=lambda x: x.stat().st_mtime, reverse=True):
    c = json.loads(f.read_text(encoding='utf-8'))
    sc = c.get('scene_id')
    print(f"Scene {sc}:")
    print("  repair_notes:", c.get('repair_notes'))
    print("  audit:", c.get('layout_audit'))
