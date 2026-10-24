"""Fill a missing provenance slot from brief metadata BEFORE existing review."""
from urllib.parse import urlsplit
from schemas.research_brief import ResearchBrief
from schemas.visual import Visual,VisualData


def ensure_source_slot(timeline):
    plan=timeline.plan
    if plan.render_style is not None and not plan.render_style.visual_templates: return
    if any(q.visual and q.visual.template=="source_card" for s in plan.scenes for q in s.shots): return
    path=timeline.project/"brief.json"
    try: brief=ResearchBrief.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError,ValueError): return
    if not brief.facts: return
    ids=list(dict.fromkeys(i for scene in plan.scenes for i in scene.fact_ids if 1<=i<=len(brief.facts))) or list(range(1,min(2,len(brief.facts))+1))
    facts=[brief.facts[i-1] for i in ids]
    names=list(dict.fromkeys(f.source_name or urlsplit(str(f.source_url)).netloc for f in facts))[:2]
    shot=plan.scenes[-1].shots[-1]
    shot.visual=Visual(template="source_card",data=VisualData(source=" · ".join(names),source_url=str(facts[0].source_url),date=facts[0].published_at or "",fact_ids=ids))
    shot.card_text=None;shot.emphasis=[];shot.text_overlay=None
    plan.review_notes.append("motion_data nhóm 2: thêm thẻ nguồn cuối từ metadata brief; tiếp tục qua kiểm tra đồ họa hiện có.")
