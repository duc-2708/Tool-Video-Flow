"""Saved paid responses must survive bad optional observations, entirely offline."""
import json
from pathlib import Path
from unittest.mock import Mock
import pytest
from schemas.style import CaptionStyle,StyleAnalysis,AnalysisRecord
from pipeline.style_raw import RawResponse,raw_path
from pipeline.style_learner import analyze_one,analyze_batch,digest_file,style_diagnostics
from pipeline.style_library import record_path
from tests.test_style_learner import style_settings

FIXTURES=Path(__file__).parent/"fixtures/style_raw"


@pytest.mark.parametrize("color,expected",[("#fa0","#FFAA00"),("#aBcD12","#ABCD12"),
    ("trắng","#FFFFFF"),("vàng chanh","#FFFF00"),("đen","#000000"),("đỏ","#FF0000"),
    ("xanh dương","#0000FF"),("xanh lá","#008000"),("xanh nhạt","#0000FF"),
    ("cam","#FFA500"),("hồng","#FFC0CB"),("tím","#800080"),("xám","#808080"),
    ("white","#FFFFFF"),("yellow","#FFFF00"),("light blue","#0000FF"),("không rõ màu",None)])
def test_named_and_unknown_colors_are_observations_not_errors(color,expected):
    captions=CaptionStyle(color=color,highlight_color=color,stroke_color=color)
    assert captions.color==captions.highlight_color==captions.stroke_color==expected
    assert color in captions.color_note and captions.analysis_warnings
    # Unknown must stay None even across JSON reloads (renderer supplies its own defaults).
    assert CaptionStyle.model_validate_json(captions.model_dump_json()).color==expected


def test_timestamps_sorted_repaired_clamped_and_optional_bad_rows_dropped():
    analysis=StyleAnalysis(duration_sec=20,hook="Câu hỏi",structure=["mở","thân","kết"],
        scenes=[{"start_sec":15,"end_sec":14,"purpose":"kết"},
            {"start_sec":0,"end_sec":0,"purpose":"hook"},
            {"start_sec":5,"end_sec":10,"purpose":"chi tiết"},
            {"start_sec":"wrong","end_sec":13,"purpose":"không thể sửa"},
            {"start_sec":30,"end_sec":35,"purpose":"ngoài video"}],
        transcript_outline=[{"start_sec":15,"end_sec":14,"summary":"kết"},
            {"start_sec":0,"end_sec":0,"summary":"mở"},{"start_sec":5,"end_sec":25,"summary":"thân"}])
    assert [(s.start_sec,s.end_sec) for s in analysis.scenes]==[(0,5),(5,10),(15,20)]
    assert all(0<=p.start_sec<p.end_sec<=20 for p in analysis.transcript_outline)
    assert any("sắp xếp" in w for w in analysis.analysis_warnings)
    assert any("loại" in w for w in analysis.analysis_warnings)
    assert any("sửa end_sec" in w for w in analysis.analysis_warnings)


def test_unrepairable_scene_dropped_but_valid_content_remains():
    analysis=StyleAnalysis(scenes=[{"start_sec":0,"end_sec":2,"purpose":"hook"},
        {"start_sec":3,"end_sec":4}])
    assert len(analysis.scenes)==1
    assert any("trường thiết yếu (purpose)" in w for w in analysis.analysis_warnings)
    with pytest.raises(ValueError,match="ít nhất 1 cảnh hợp lệ"):
        StyleAnalysis(scenes=[{"start_sec":0,"end_sec":0,"purpose":"cannot infer duration"}])


def test_optional_types_bounds_and_nested_errors_use_defaults_with_paths():
    analysis=StyleAnalysis(scenes=[{"start_sec":"0","end_sec":"3","purpose":"hook",
        "shot_count":"không rõ","average_shot_sec":999,"word_count":-10,
        "overlays":[{"text":["chữ","nhấn"],"position":{"name":"top"}}],
        "music":{"description":"êm"},"transition_to_next":123}],
        captions={"font_description":["Arial","đậm"],"font_scale":"huge","position":"không xác định", "mode":"unknown"},
        pacing={"pattern_interrupts":["bad"]},audio={"music_volume":5,"sfx_per_10_sec":"not a number"},
        narration_style={"words_per_sec":999,"average_sentence_words":"12","humor":["nhẹ","nhàng"]},
        suggested_type="invented",strengths=123)
    assert analysis.scenes[0].shot_count is None and analysis.scenes[0].word_count is None
    assert analysis.scenes[0].average_shot_sec is None
    assert analysis.scenes[0].overlays[0].text=="chữ; nhấn"
    assert analysis.captions.font_scale==.064 and analysis.captions.position=="lower"
    assert analysis.captions.mode=="phrase" and analysis.captions.font_description=="Arial; đậm"
    assert analysis.audio.music_volume==.08 and analysis.audio.sfx_per_10_sec==0
    assert analysis.narration_style.words_per_sec is None
    assert analysis.narration_style.average_sentence_words==12
    assert analysis.suggested_type is None and analysis.strengths==[]
    assert any("captions.font_scale" in w for w in analysis.analysis_warnings)
    assert any("audio.music_volume" in w for w in analysis.analysis_warnings)
    assert any("scenes.0.word_count" in w for w in analysis.analysis_warnings)


@pytest.mark.parametrize("name,duration,scene_count",[("cong_nghe_2",116.71,4),("cong_nghe_4",89.12,6)])
def test_real_cong_nghe_raw_recovers_offline_and_persists_done_with_warnings(style_settings,monkeypatch,name,duration,scene_count):
    source=FIXTURES/(name+".raw.txt")
    original=source.read_bytes()
    video=style_settings.root_dir/"assets/reference_videos/cong-nghe"/(name+".mp4")
    video.parent.mkdir();video.write_bytes(name.encode("ascii"))
    monkeypatch.setattr("pipeline.style_learner.inspect_video",lambda p,s:{"duration_sec":duration,"size_bytes":p.stat().st_size})
    target=raw_path(style_settings,"cong-nghe",digest_file(video))
    target.parent.mkdir(parents=True);target.write_bytes(original)
    no_api=Mock(side_effect=AssertionError("--from-raw must never use Gemini"))
    monkeypatch.setattr("pipeline.style_learner.VideoStyleProvider",no_api)
    results=analyze_batch(style_settings,["cong-nghe/"+name+".mp4"],from_raw=True)
    result=results[0]
    assert result["status"]=="cached" and result["status_label"]=="done (có cảnh báo)"
    assert result["warning_count"]>0 and result["error"] is None
    analysis=result["analysis"]
    assert len(analysis["scenes"])==scene_count
    assert analysis["analysis_warnings"] and analysis["duration_sec"]==duration
    assert all(0<=s["start_sec"]<s["end_sec"]<=duration for s in analysis["scenes"])
    assert analysis["captions"]["color"].startswith("#") and analysis["captions"]["color_note"]
    saved=AnalysisRecord.model_validate_json(record_path(style_settings,"cong-nghe/"+name+".mp4").read_text(encoding="utf-8"))
    assert set(saved.analysis.analysis_warnings)<=set(saved.warnings)
    assert target.read_bytes()==original==source.read_bytes()
    from db.repository import Repository
    assert Repository.for_settings(style_settings).video("cong-nghe","local",digest_file(video))["status"]=="done"
    status=json.loads(record_path(style_settings,"cong-nghe/"+name+".mp4",status=True).read_text(encoding="utf-8"))
    assert status["status_label"]=="done (có cảnh báo)" and status["warning_count"]>0
    no_api.assert_not_called()


def test_measured_scope_overrides_wrong_raw_duration_and_compact_is_also_tolerant(style_settings):
    store=RawResponse(raw_path(style_settings,None,"a"*64),{},style_diagnostics(style_settings),duration_limit=8)
    store.mode="compact"
    store.save(json.dumps({"duration_sec":30,"scenes":[{"start_sec":0,"end_sec":7,"purpose":"hook"},
        {"start_sec":7,"end_sec":6,"purpose":"ending","shot_count":"bad"}],"narrative_flow":{"name":"mở → kết"}}))
    result=store.parse()
    assert result.duration_sec==8 and result.scenes[-1].end_sec==8
    assert result.scenes[-1].shot_count is None and result.analysis_warnings


def test_repaired_diagnostics_and_original_color_notes_do_not_leak_to_director():
    from pipeline.style_profile import aggregate,guidance
    from tests.test_style_learner import record
    sample=record()
    sample.analysis.captions=CaptionStyle(color="màu vàng chanh")
    data=guidance(aggregate([sample],"test"))
    assert "color_note" not in data["captions"] and "analysis_warnings" not in data["captions"]
    assert "analysis_warnings" not in data["audio"]
