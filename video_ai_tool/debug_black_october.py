import json
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
from schemas.assets import ResolvedEditPlan
from schemas.research_brief import ResearchBrief
from agents.visual_diversity import select_templates, repair_numeric_cards
from config.settings import ROOT_DIR

FIXTURE = ROOT_DIR / 'tests/fixtures/black_october'
plan = ResolvedEditPlan.model_validate_json((FIXTURE / 'edit_plan.resolved.json').read_text(encoding='utf-8'))
brief = ResearchBrief.model_validate_json((FIXTURE / 'brief.json').read_text(encoding='utf-8'))

select_templates(plan, brief)
repair_numeric_cards(plan, brief)

for s_idx, s in enumerate(plan.scenes):
    for sh_idx, shot in enumerate(s.shots):
        if shot.visual and shot.visual.template not in {'stock', 'source_card', 'quote_card'}:
            words = (shot.card_text or '').split()
            print(f"Scene {s_idx} Shot {sh_idx}: template={shot.visual.template}, card_text='{shot.card_text}', len={len(words)}")
