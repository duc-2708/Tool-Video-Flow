import json
from pathlib import Path
project_dir = Path('output/auto-cong-nghe-b02014fc')
cache_meta_files = sorted(project_dir.glob('**/*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
for sc_id in (2, 3):
    for mf in cache_meta_files:
        if mf.name in {'edit_plan.json', 'director_state.json', 'quality_report.json', 'layout_report.json', 'visual_review.json', 'preview.json', 'motion_review.json', 'motion_plan.json'}:
            continue
        if mf.name.endswith('.json'):
            try:
                c = json.loads(mf.read_text(encoding='utf-8'))
                if isinstance(c, dict) and c.get('scene_id') == sc_id and 'layout_audit' in c:
                    la = c['layout_audit']
                    print(f"Scene {sc_id} matched file {mf.name} with clipped_rows={la.get('clipped_rows')}")
                    break
            except Exception:
                pass
