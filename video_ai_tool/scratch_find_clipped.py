import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

from editor.render import build_timeline
from pipeline.render_motion import scene_payload, html_document
from schemas.edit_plan import EditPlan

p = Path('output/auto-cong-nghe-b02014fc')
raw_plan = json.loads((p / 'edit_plan.resolved.json').read_text(encoding='utf-8'))
for k in ['source_plan_hash', 'timing_basis', 'warnings', 'review_notes']:
    raw_plan.pop(k, None)
plan = EditPlan.model_validate(raw_plan)
audio_dir = p / 'audio'
audios = {int(f.stem.replace('scene_', '')): f for f in audio_dir.glob('scene_*.mp3')}
clips_dir = p / 'clips'
clips = {int(f.stem.split('_')[1]): f for f in clips_dir.glob('scene_*.mp4')}

timeline = build_timeline(p / 'edit_plan.resolved.json')
print(f"Total scenes in timeline: {len(timeline.scenes)}")

font = list(Path('.').glob('**/*.ttf'))[0]
dummy_cap = type('Cap', (), {'model_dump': lambda self, mode='json': {'enabled': True, 'font_size': 48}})()

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1080, "height": 1920})
    for sc in timeline.scenes:
        if sc.spec.id in (2, 3):
            payload = scene_payload(sc, (1080, 1920), dummy_cap)
            doc = html_document(payload, font)
            page.set_content(doc)
            page.evaluate("() => window.renderAt(2.0)")
            clipped = page.evaluate("""() => {
                const illustration = document.querySelector('.scene-illustration');
                const svgEl = illustration.querySelector('svg');
                const svgRect = svgEl.getBoundingClientRect();
                const scaleX = 1080 / svgRect.width;
                const scaleY = 1920 / svgRect.height;
                function getGlobalBBox(el) {
                    const r = el.getBoundingClientRect();
                    return {
                        x: Math.round((r.left - svgRect.left) * scaleX),
                        y: Math.round((r.top - svgRect.top) * scaleY),
                        width: Math.round(r.width * scaleX),
                        height: Math.round(r.height * scaleY)
                    };
                }
                const elementsToCheck = [...illustration.querySelectorAll('rect, text, .ill-label, .motion-element')];
                const res = [];
                elementsToCheck.forEach(el => {
                    if (el.classList.contains('depth-background') || el.closest('.depth-background')) return;
                    const b = getGlobalBBox(el);
                    if (b.width > 0 && b.height > 0) {
                        if (b.x + b.width > 1015 || b.x < 65 || b.y + b.height > 1335 || b.y < 235) {
                            res.push({
                                tag: el.tagName,
                                cls: String(el.className?.baseVal || el.className || ''),
                                txt: (el.textContent || '').trim().slice(0, 30),
                                box: b,
                                viol: {
                                    left: b.x < 65,
                                    right: b.x + b.width > 1015,
                                    top: b.y < 235,
                                    bottom: b.y + b.height > 1335
                                }
                            });
                        }
                    }
                });
                return res;
            }""")
            print(f"=== Scene {sc.spec.id} clipped ({len(clipped)}): ===")
            for c in clipped:
                print(" ", c)
    browser.close()
