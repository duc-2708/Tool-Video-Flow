import json
from pathlib import Path
from pipeline.render_motion import browser_page, capture
from editor.captions import find_font
from config.settings import ROOT_DIR

font = find_font(ROOT_DIR)

for sc_file in ['e6bc964aeb9acbca353f801435ff82c450f461a6a1427af336492b7d344c5fcd.json', 'b8021d4cb53ea5746b8725a7b7a03fbbdb6fadd8f71a9e151ab06f07a02435cf.json']:
    data = json.loads(Path('output/auto-cong-nghe-b02014fc/render/motion_cache', sc_file).read_text(encoding='utf-8'))
    payload = data.get('payload')
    if not payload:
        continue
    print(f"=== Scene {data.get('scene_id')} ===")
    with browser_page((1080, 1920)) as page:
        capture(page, payload, font)
        clipped_details = page.evaluate("""() => {
            const ill = document.getElementById('illustration');
            const items = [];
            const elementsToCheck = [...ill.querySelectorAll('rect, text, .ill-label, .motion-element')];
            elementsToCheck.forEach(el => {
                if (el.closest('clipPath')) return;
                const clipContainer = el.closest('[clip-path]');
                if (clipContainer) {
                    const cb = window.getGlobalBBox(clipContainer);
                    if (cb.width > 0 && cb.height > 0 && cb.x >= 65 && cb.x + cb.width <= 1015 && cb.y >= 235 && cb.y + cb.height <= 1335) {
                        return;
                    }
                }
                const b = window.getGlobalBBox(el);
                if (b.width > 0 && b.height > 0) {
                    if (b.x + b.width > 1015 || b.x < 65 || b.y + b.height > 1335 || b.y < 235) {
                        if (!el.classList.contains('depth-background') && !el.closest('.depth-background')) {
                            items.push({
                                tag: el.tagName,
                                class: el.getAttribute('class'),
                                text: el.textContent ? el.textContent.trim().slice(0, 30) : '',
                                bbox: {x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height)}
                            });
                        }
                    }
                }
            });
            return items;
        }""")
        print(json.dumps(clipped_details, indent=2, ensure_ascii=False))
