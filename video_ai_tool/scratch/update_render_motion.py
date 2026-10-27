import re
from pathlib import Path

motion_path = Path("pipeline/render_motion.py")
code = motion_path.read_text(encoding="utf-8")

old_block = """                layout_audit = page.evaluate("() => window.getLayoutAudit ? window.getLayoutAudit() : null")
                final_source=next((s for s in reversed(payload["shots"]) if s["template"]=="source_card"),None)"""

new_block = """                layout_audit = page.evaluate("() => window.getLayoutAudit ? window.getLayoutAudit() : null")
                audit_passed = bool(
                    layout_audit and
                    layout_audit.get("clipped_rows", 0) == 0 and
                    layout_audit.get("bbox_overlaps", 0) == 0 and
                    layout_audit.get("caption_collisions", 0) == 0 and
                    layout_audit.get("empty_prompts", 0) == 0 and
                    layout_audit.get("center_y_drift", 0) <= 120
                )
                audit_retries = 0
                while not audit_passed and audit_retries < 2:
                    audit_retries += 1
                    if audit_retries == 1:
                        page.evaluate('''() => {
                            if (window.MOTION_DATA && window.MOTION_DATA.visual_plan && window.MOTION_DATA.visual_plan.data) {
                                const d = window.MOTION_DATA.visual_plan.data;
                                if (d.items) {
                                    d.items = d.items.map(s => String(s).split(/[.!?\\\\n]/)[0].split(/\\\\s+/).slice(0, 5).join(' '));
                                }
                                if (window.renderAt) window.renderAt(2.0);
                            }
                        }''')
                    elif audit_retries == 2:
                        page.evaluate('''() => {
                            if (window.MOTION_DATA && window.MOTION_DATA.visual_plan) {
                                window.MOTION_DATA.visual_plan.scene_type = 'text_focus';
                                if (window.renderAt) window.renderAt(2.0);
                            }
                        }''')
                    layout_audit = page.evaluate("() => window.getLayoutAudit ? window.getLayoutAudit() : null")
                    audit_passed = bool(
                        layout_audit and
                        layout_audit.get("clipped_rows", 0) == 0 and
                        layout_audit.get("bbox_overlaps", 0) == 0 and
                        layout_audit.get("caption_collisions", 0) == 0 and
                        layout_audit.get("empty_prompts", 0) == 0 and
                        layout_audit.get("center_y_drift", 0) <= 120
                    )
                final_source=next((s for s in reversed(payload["shots"]) if s["template"]=="source_card"),None)"""

code = code.replace(old_block, new_block)
code = code.replace(
    '"layout_audit":layout_audit,',
    '"layout_audit":layout_audit,"audit_failed":not audit_passed,"audit_retries":audit_retries,'
)

motion_path.write_text(code, encoding="utf-8")
print("Updated pipeline/render_motion.py")
