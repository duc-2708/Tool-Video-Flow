import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

p = Path('output/auto-cong-nghe-b02014fc/render/motion_cache')
meta_files = sorted(p.glob('*.json'), key=lambda x: x.stat().st_mtime, reverse=True)

for mf in meta_files:
    c = json.loads(mf.read_text(encoding='utf-8'))
    sc_id = c.get('scene_id')
    if sc_id == 2:
        print("Meta scene 2 audit:", c.get('layout_audit'))
    elif sc_id == 3:
        print("Meta scene 3 audit:", c.get('layout_audit'))
