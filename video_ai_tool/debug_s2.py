import json
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
from config.settings import ROOT_DIR

FIXTURE = ROOT_DIR / 'tests/fixtures/black_october'
raw = json.loads((FIXTURE / 'edit_plan.resolved.json').read_text(encoding='utf-8'))
s2 = raw['scenes'][2]
print("Narration:", s2.get('narration'))
for sh_idx, shot in enumerate(s2.get('shots', [])):
    print(f"Shot {sh_idx}: card_text='{shot.get('card_text')}', template={shot.get('visual', {}).get('template') if shot.get('visual') else None}")
