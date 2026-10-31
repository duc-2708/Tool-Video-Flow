import json
from pathlib import Path
p = Path('output/auto-cong-nghe-b02014fc/render/motion_cache')
for f in sorted(p.glob('*.json'), key=lambda x: x.stat().st_mtime, reverse=True):
    c = json.loads(f.read_text(encoding='utf-8'))
    sc = c.get('scene_id')
    la = c.get('layout_audit', {})
    print(f"Scene {sc}: clipped_rows={la.get('clipped_rows')}, hero_w={la.get('hero_width')}")
