import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding='utf-8')
from playwright.sync_api import sync_playwright
from config.settings import get_settings
from pipeline.render_motion import html_document, scene_payload
from editor.render import find_font
from schemas.edit_plan import EditPlan
from editor.timeline import Timeline
from pipeline.motion_batch import scene_options
from editor.motion.theme import load_motion_theme, mascot_uris

settings = get_settings()
font = find_font(settings.root_dir)

plan_path = Path('output/auto-tin-tuc-0ab515f6/edit_plan.json')
with open(plan_path, encoding='utf-8') as f:
    plan_dict = json.load(f)

timeline = Timeline(plan_path.parent, EditPlan.model_validate(plan_dict))
theme = load_motion_theme(settings.root_dir, timeline.plan, settings.motion_theme)
mascots = mascot_uris(settings.root_dir, states=('idle','point','shrug','surprised','think','thinking'))

with sync_playwright() as p:
    browser = p.chromium.launch()
    for scene in timeline.scenes:
        opts = scene_options(timeline, scene, theme, mascots)
        opts.update(illustrations_enabled=True, min_card_hold_sec=1.2)
        payload = scene_payload(scene, (1080, 1920), timeline.plan.render_style.caption_style or {}, options=opts)
        html = html_document(payload, font)
        page = browser.new_page(viewport={'width': 1080, 'height': 1920})
        page.set_content(html)
        info = page.evaluate('''() => {
            renderAt(3.0);
            const ill = document.querySelector('.scene-illustration');
            const cap = document.querySelector('#captions');
            const mas = document.querySelector('.action-mascot');
            const src = document.querySelector('.scene-source');
            const rects = [];
            document.querySelectorAll('.scene-illustration rect, .scene-illustration text, .scene-illustration circle, .scene-illustration path').forEach(el => {
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.height > 0 && !el.classList.contains('depth-background') && !el.closest('.depth-background')) {
                    rects.push({tag: el.tagName, text: el.textContent?.slice(0, 20), x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)});
                }
            });
            const capR = cap?.getBoundingClientRect();
            const masR = mas?.getBoundingClientRect();
            const srcR = src?.getBoundingClientRect();
            const illR = ill?.getBoundingClientRect();
            return {
                stype: window.MOTION_DATA?.visual_plan?.scene_type,
                ill: illR ? {x: Math.round(illR.x), y: Math.round(illR.y), w: Math.round(illR.width), h: Math.round(illR.height)} : null,
                all_y: [Math.min(...rects.map(r=>r.y)), Math.max(...rects.map(r=>r.y+r.h))],
                all_x: [Math.min(...rects.map(r=>r.x)), Math.max(...rects.map(r=>r.x+r.w))],
                cap: capR ? {x: Math.round(capR.x), y: Math.round(capR.y), w: Math.round(capR.width), h: Math.round(capR.height)} : null,
                mas: masR ? {x: Math.round(masR.x), y: Math.round(masR.y), w: Math.round(masR.width), h: Math.round(masR.height)} : null,
                src: srcR ? {x: Math.round(srcR.x), y: Math.round(srcR.y), w: Math.round(srcR.width), h: Math.round(srcR.height), display: getComputedStyle(src).display} : null
            };
        }''')
        print(f"Scene {scene.spec.id} ({info['stype']}):")
        print(f"  Illustration: {info['ill']}")
        print(f"  Graphic BBox X: {info['all_x']}, Y: {info['all_y']}")
        print(f"  Captions: {info['cap']}")
        print(f"  Mascot: {info['mas']}")
        print(f"  Source: {info['src']}")
        page.close()
    browser.close()
