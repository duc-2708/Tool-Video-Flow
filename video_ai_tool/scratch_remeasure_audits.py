import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

from editor.render import build_timeline
from pipeline.render_motion import scene_payload, html_document

p = Path('output/auto-cong-nghe-b02014fc')
timeline = build_timeline(p / 'edit_plan.resolved.json')
font = list(Path('.').glob('**/*.ttf'))[0]
dummy_cap = type('Cap', (), {'model_dump': lambda self, mode='json': {'enabled': True, 'font_size': 48}})()

cache_dir = p / 'render/motion_cache'
meta_files = list(cache_dir.glob('*.json'))

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1080, "height": 1920})
    for sc in timeline.scenes:
        payload = scene_payload(sc, (1080, 1920), dummy_cap)
        doc = html_document(payload, font)
        page.set_content(doc)
        audit = page.evaluate("() => window.getLayoutAudit()")
        print(f"Scene {sc.spec.id} measured layout_audit:")
        print(" ", audit)
        # Update matching meta file
        for mf in meta_files:
            c = json.loads(mf.read_text(encoding='utf-8'))
            if c.get('scene_id') == sc.spec.id:
                c['layout_audit'] = audit
                mf.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding='utf-8')
    browser.close()

print("All scene audits measured and updated from real DOM!")
