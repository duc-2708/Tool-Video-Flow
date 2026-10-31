import json
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
from schemas.assets import ResolvedEditPlan
from schemas.research_brief import ResearchBrief
from agents.visual_diversity import numeric_mismatches, shot_context
from config.settings import ROOT_DIR

FIXTURE = ROOT_DIR / 'tests/fixtures/black_october'
plan = ResolvedEditPlan.model_validate_json((FIXTURE / 'edit_plan.resolved.json').read_text(encoding='utf-8'))
brief = ResearchBrief.model_validate_json((FIXTURE / 'brief.json').read_text(encoding='utf-8'))

s2 = plan.scenes[2]
shot3 = s2.shots[3]
print("shot3 card_text:", repr(shot3.card_text))
print("bad:", numeric_mismatches(s2, shot3, brief))
ctx = shot_context(s2, shot3)
print("shot_context:", repr(ctx))
clean_ctx = __import__('re').sub(r'\d+(?:[.,]\d+)*', '', ctx)
print("clean_ctx:", repr(clean_ctx))
from agents.visual_diversity import concept_card
print("concept_card result:", repr(concept_card(clean_ctx)))
