"""Offline Pillow/MoviePy templates, provenance, selection and safe layout."""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from editor.templates import NAMES,load_theme
from editor.templates.core import number_at,element_times
from schemas.visual import Visual,VisualData
from schemas.research_brief import ResearchBrief
from schemas.edit_plan import EditPlan
from schemas.style import StyleRenderDefaults,CaptionStyle
from agents.visual_planner import assign_visuals,visual_issues
from agents.validation_rules import Context,visual_grounding,RuleViolation,run_rules
from tests.test_director import fixture_brief,fixture_plan


@pytest.mark.parametrize("name",NAMES)
@pytest.mark.parametrize("size",[(270,480),(480,270)])
def test_every_template_missing_or_long_data(name,size):
    render=importlib.import_module("editor.templates."+name).render
    for data in ({},{"text":"Giải thích dữ kiện rất dài "*80,"highlight":["dữ"],"value":5000,"label":"nhãn "*100,
            "source":"Nguồn "*100,"items":["dữ liệu "*70]*4,
            "bars":[{"label":"giá trị "*80,"value":v} for v in (0,-1,999999)]}):
        clip=render(data,5,size,load_theme())
        try:
            assert clip.duration==5 and tuple(clip.size)==size
            for t in (0,.2,2,4.95):
                frame=clip.get_frame(t)
                assert frame.shape==(size[1],size[0],3) and frame.dtype==np.uint8
            assert not np.array_equal(clip.get_frame(1),clip.get_frame(4.5))
        finally: clip.close()


def test_stat_counter_exact_and_monotone():
    values=[number_at(5000,t,3) for t in np.linspace(0,2.9,30)]
    assert values[0]==0 and values[-1]==5000 and sorted(values)==values


def test_reveals_and_refresh_no_static_four_seconds():
    for name in NAMES:
        clip=importlib.import_module("editor.templates."+name).render({"text":"Đọc sâu dữ liệu","items":["A","B","C","D"]},12,(270,480))
        try:
            for t in (1,4,7): assert not np.array_equal(clip.get_frame(t),clip.get_frame(t+.5))
            assert all(b-a<=3 for a,b in zip(clip.visual_card.events,clip.visual_card.events[1:]))
        finally: clip.close()


def fixture():
    brief=ResearchBrief.model_validate(fixture_brief())
    brief.facts.append(brief.facts[0].model_copy(deep=True))
    plan=EditPlan.model_validate(fixture_plan())
    return plan,brief


def test_auto_selection_and_only_two_source_cards():
    plan,brief=fixture()
    brief.facts[0].fact_vi="Sản phẩm có 5.000 người dùng."
    for scene in plan.scenes: scene.fact_ids=[1]
    assign_visuals(plan,brief)
    templates=[s.visual.template for c in plan.scenes for s in c.shots]
    assert templates[0]=="hook_card" and templates.count("source_card")==2
    assert "stat_card" in templates and "text_focus" in templates
    assert not visual_issues(plan,brief)


def test_visual_fabricated_number_and_source_still_hard_fail():
    plan,brief=fixture()
    shot=plan.scenes[1].shots[0]
    shot.visual=Visual(template="stat_card",data=VisualData(value=987654321,label="Số liệu",fact_ids=[1]))
    findings=visual_grounding(Context(plan,brief))
    assert findings and "987654321" in findings[0].message
    with pytest.raises(RuleViolation,match="visual_grounding"):
        run_rules(plan,brief,check_style=False,allow_merge=False)
    shot.visual=Visual(template="source_card",data=VisualData(source="Nguồn bịa",source_url="https://madeup.invalid/",fact_ids=[1]))
    assert any("nguồn" in text.lower() for _,text in visual_issues(plan,brief))


def test_steps_and_comparison_only_when_fact_supports_it():
    plan,brief=fixture()
    brief.facts[0].fact_vi="Tỷ lệ cũ là 30%."
    brief.facts[1].fact_vi="Tỷ lệ mới là 75%, so với mức cũ."
    scene=plan.scenes[2];scene.fact_ids=[1,2]
    assign_visuals(plan,brief)
    assert any(s.visual.template=="compare_bars" for s in scene.shots)
    assert not visual_issues(plan,brief)
    for s in scene.shots: s.visual=None
    brief.facts[0].fact_vi="Kiểm tra nguồn và ngày đăng."
    brief.facts[1].fact_vi="Đọc toàn bộ bài viết."
    scene.narration="Các bước bao gồm kiểm tra nguồn và đọc bài viết."
    assign_visuals(plan,brief)
    assert any(s.visual.template=="steps_list" for s in scene.shots)


def test_pill_caption_stays_clear_of_card(tmp_path):
    from editor.captions import Captions,find_font
    from config.settings import ROOT_DIR
    shot=SimpleNamespace(spec=SimpleNamespace(visual=Visual(template="text_focus")),start=0,duration=8)
    scene=SimpleNamespace(start=0,duration=8,audio=tmp_path/"voice.mp3",audio_silent=False,shots=[shot],spec=SimpleNamespace(narration="Một câu phụ đề nằm trong vùng an toàn"))
    timeline=SimpleNamespace(scenes=[scene],plan=SimpleNamespace(render_style=StyleRenderDefaults(captions=CaptionStyle(appearance="pill",position="center"))))
    caption=Captions(timeline,(540,960),find_font(ROOT_DIR)).overlay(1)
    bbox=caption.getbbox()
    assert bbox and bbox[1]>=960*.64 and bbox[3]<960*.83


def test_theme_image_never_escapes_backgrounds(tmp_path):
    from editor.templates.theme import background
    theme=load_theme();theme.update(root=str(tmp_path),image="../../secret.png")
    assert background((40,60),theme).size==(40,60)
