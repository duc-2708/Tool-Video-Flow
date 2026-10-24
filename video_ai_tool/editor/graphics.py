"""Read-only graphics preparation and a persistent progress tracker."""
import json
from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np
from schemas.style import StyleRenderDefaults
from editor.templates.core import font,short,text_block
from editor.templates.theme import load_theme


def prepare_graphics(timeline,diagnostics=None):
    plan=timeline.plan
    style=plan.render_style or StyleRenderDefaults()
    # Resolve options in memory only; all project input files stay immutable.
    plan.render_style=style
    if not style.visual_templates: return
    brief_path=timeline.project/"brief.json"
    brief=None
    if brief_path.is_file():
        from schemas.research_brief import ResearchBrief
        from agents.visual_planner import assign_visuals
        try:
            brief=ResearchBrief.model_validate_json(brief_path.read_text(encoding="utf-8"))
            assign_visuals(plan,brief)
        except Exception as error:
            brief=None
            if diagnostics: diagnostics.record_exception(error,"Không đọc/chuẩn bị được brief đồ họa; dùng bản trung tính")
            timeline.warnings.append("Không đọc được brief đồ họa; các thẻ sự kiện được thay trung tính.")
    # Cap auto source cards before applying explicit editorial decisions.
    cards=[s for c in plan.scenes for s in c.shots if s.visual and s.visual.template=="source_card"]
    for shot in cards[:-1]:
        from schemas.visual import Visual,VisualData
        shot.visual=Visual(template="text_focus",data=VisualData(text=shot.text_overlay or "Thông tin từ nguồn"))
    from agents.presentation import source_card_once,normalize_cards
    # Surface new card_text to the established provenance policy before painting.
    source_card_once(plan,brief);normalize_cards(plan,brief,diagnostics=diagnostics)
    from agents.visual_policy import review_for_render,load_decisions
    try: decisions=load_decisions(timeline.project)
    except Exception as error:
        decisions={}
        if diagnostics: diagnostics.record_exception(error,"Đọc lựa chọn đồ họa; dùng chính sách trung tính")
        timeline.warnings.append("Không đọc được lựa chọn đồ họa; dùng chính sách trung tính mặc định.")
    timeline.visual_review=review_for_render(plan,brief,decisions)
    for item in timeline.visual_review:
        if item["action"]=="neutral":
            scene=next(s for s in plan.scenes if s.id==item["scene_id"])
            shot=scene.shots[item["shot_id"]-1]
            shot.card_text=None;shot.emphasis=[]  # Cannot resurrect rejected text after neutralization.
    source_card_once(plan,brief);normalize_cards(plan,brief,diagnostics=diagnostics)
    for item in timeline.visual_review:
        for message in item["warnings"]:
            warning=f"Cảnh {item['scene_id']}: {message}"
            if warning not in timeline.warnings: timeline.warnings.append(warning)
            if diagnostics: diagnostics.record("Đồ họa: "+warning)
            from schemas.edit_plan import ReviewNotes
            scene=next(s for s in plan.scenes if s.id==item["scene_id"])
            if scene.review_notes is None:
                scene.review_notes=ReviewNotes(fact_ids=scene.fact_ids,source_count=0,confidence=None,facts=[])
            if warning not in scene.review_notes.warnings: scene.review_notes.warnings.append(warning)
    # Presentation repairs happen after the established factual policy. No
    # change to group-1 checks or the immutable resolved plan on disk.
    from agents.visual_diversity import select_templates,repair_numeric_cards
    repair_numeric_cards(plan,brief)
    select_templates(plan,brief)


class ProgressTracker:
    def __init__(self,timeline,size,theme):
        self.timeline,self.size,self.theme=timeline,size,theme
        self.enabled=bool(timeline.plan.render_style and timeline.plan.render_style.progress_tracker)
        self.labels=(timeline.plan.render_style.progress_labels if timeline.plan.render_style else [])
        self.cache={}

    def apply(self,frame,t):
        if not self.enabled: return frame
        scenes=self.timeline.scenes
        current=next((i for i,s in enumerate(scenes) if t<s.start+s.duration),len(scenes)-1)
        if current not in self.cache:
            w,h=self.size;layer=Image.new("RGBA",self.size);draw=ImageDraw.Draw(layer)
            # At most six groups on narrow phones; all scene IDs still map to a group.
            n=min(6,len(scenes));active=min(n-1,current*n//len(scenes));margin=w*.09
            positions=np.linspace(margin,w-margin,n)
            yy=h*.065;r=w*.010
            draw.line([(margin,yy),(w-margin,yy)],fill=self.theme["muted"],width=max(2,round(w*.003)))
            for i,x in enumerate(positions):
                color=self.theme["accent"] if i<=active else self.theme["muted"]
                draw.ellipse((x-r,yy-r,x+r,yy+r),fill=color)
                label=self.labels[i] if i<len(self.labels) else scenes[min(len(scenes)-1,i*len(scenes)//n)].spec.style_purpose or ("Mở đầu" if i==0 else "Kết" if i==n-1 else f"Ý {i}")
                text_block(draw,short(label,20),(x-w*.07,yy+h*.016,w*.14,h*.035),self.theme,.23,fill=color)
            self.cache[current]=layer
        return np.asarray(Image.alpha_composite(Image.fromarray(frame).convert("RGBA"),self.cache[current]).convert("RGB"))
