import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

p = Path('output/auto-cong-nghe-b02014fc')
plan = json.loads((p / 'edit_plan.resolved.json').read_text(encoding='utf-8'))
from pipeline.render_motion import scene_payload, html_document
from config.settings import get_settings
from schemas.edit_plan import Scene
from editor.render import TimelineScene

settings = get_settings()
font = "assets/fonts/BeVietnamPro-Bold.ttf"
if not Path(font).is_file():
    font = list(Path('.').glob('**/*.ttf'))[0]

sc3 = plan['scenes'][2]
scene_obj = Scene.model_validate(sc3)
tl_scene = TimelineScene(scene_obj, 0.0, 10.0, Path("output/auto-cong-nghe-b02014fc/audio/scene_3.mp3"))

payload = scene_payload(tl_scene, (1080, 1920), settings.captions.style)
html = html_document(payload, font)

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1080, "height": 1920})
    page.set_content(html)
    page.evaluate("() => window.renderAt(2.0)")
    res = page.evaluate("""() => {
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
        const clipped = [];
        elementsToCheck.forEach(el => {
            if (el.classList.contains('depth-background') || el.closest('.depth-background')) return;
            const b = getGlobalBBox(el);
            if (b.width > 0 && b.height > 0) {
                if (b.x + b.width > 1015 || b.x < 65 || b.y + b.height > 1335 || b.y < 235) {
                    clipped.push({
                        tag: el.tagName,
                        cls: String(el.className?.baseVal || el.className || ''),
                        text: (el.textContent || '').trim().slice(0, 30),
                        bbox: b
                    });
                }
            }
        });
        return clipped;
    }""")
    print("Total clipped in Scene 3:", len(res))
    for r in res:
        print(" ", r)
    browser.close()
