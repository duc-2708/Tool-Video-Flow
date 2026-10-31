import json
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
from schemas.assets import ResolvedEditPlan
from schemas.research_brief import ResearchBrief
from agents.visual_diversity import repair_cards, shot_context, concept_card
from config.settings import ROOT_DIR

FIXTURE = ROOT_DIR / 'tests/fixtures/black_october'
plan = ResolvedEditPlan.model_validate_json((FIXTURE / 'edit_plan.resolved.json').read_text(encoding='utf-8'))
brief = ResearchBrief.model_validate_json((FIXTURE / 'brief.json').read_text(encoding='utf-8'))

# Trace repair_cards step by step
history = []
for scene in plan.scenes:
    for index, shot in enumerate(scene.shots, 1):
        v = shot.visual
        if not v or v.template in {'stock', 'source_card', 'quote_card'}: continue
        old = shot.card_text or v.data.text or v.data.label
        if scene.id == plan.scenes[2].id and index == 4:
            print("At Scene 2 Shot 3:")
            print("  context:", repr(shot_context(scene, shot)))
            print("  history[-2:]:", repr(history[-2:]))
            res, is_clause = concept_card(shot_context(scene, shot), history[-2:])
            print("  concept_card res:", repr(res), "is_clause:", is_clause)
        history.append(shot.card_text or v.data.text)
