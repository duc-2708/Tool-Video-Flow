"""Flexible style observations and bounded compact retries, with no real APIs."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from google.genai import types
from config.settings import ROOT_DIR
from schemas.style import ObservedScene,StyleAnalysis
from pipeline.style_raw import RawResponse,StyleRawError,raw_path,reuse_raw
from pipeline.style_learner import VideoStyleProvider,analyze_one,analyze_batch,style_diagnostics,digest_file
from tests.test_style_learner import style_settings,observed


@pytest.mark.parametrize("value",[None,"","none","không có","n/a","fade","fade: Nhưng điều đáng nói là...",{"kind":"fade","connective":"Nhưng..."},{"type":"cut","connective_template":""}])
def test_transition_null_string_and_dictionary(value):
    scene=ObservedScene(start_sec="0",end_sec="2.5",purpose="hook",transition_to_next=value)
    if value in (None,"","none","không có","n/a"):
        assert scene.transition_to_next is None
    else:
        assert scene.transition_to_next.type in {"cut","fade"}
        assert scene.transition_to_next.kind==scene.transition_to_next.type
    plan=StyleAnalysis(scenes=[{"start_sec":0,"end_sec":2.5,"purpose":"hook","transition_to_next":value}])
    assert plan.scenes[-1].transition_to_next is None


def test_only_three_scene_fields_required_and_common_model_type_variations():
    required={k for k,v in ObservedScene.model_fields.items() if v.is_required()}
    assert required=={"start_sec","end_sec","purpose"}
    data=StyleAnalysis(scenes=[{"start_sec":"00:00","end_sec":"00:03","purpose":["hook"],
        "narration_summary":["Một ý","Một ví dụ"],"shot_count":"2","word_count":"6",
        "visual_types":"b-roll","overlays":["Từ khóa"],"music":["nhẹ","êm"]}],
        hook="Câu hỏi",narrative_flow=["hook","kết"],narration_style={"pronouns":"bạn","examples":["Ví dụ 1","Ví dụ 2"]},
        pacing={"average_shot_sec":"1.5"},visual_style="stock video",audio="Nhạc nền nhẹ")
    scene=data.scenes[0]
    assert scene.shot_count==2 and scene.word_count==6 and scene.average_shot_sec==1.5
    assert scene.overlays[0].text=="Từ khóa" and scene.visual_types==["b-roll"]
    assert data.duration_sec==3 and data.structure and data.narrative_flow=="hook; kết"
    minimal=StyleAnalysis(scenes=[{"start_sec":0,"end_sec":3,"purpose":"hook"}])
    assert minimal.scenes[0].word_count is None and minimal.scenes[0].shot_count is None
    assert minimal.pacing.average_shot_sec is None
    with pytest.raises(ValueError):
        StyleAnalysis(scenes=[{"start_sec":"wrong","end_sec":3,"purpose":"hook"}])


@pytest.mark.parametrize("case",["duration","count","average"])
def test_nonessential_timeline_headers_normalize_with_explicit_notes(case):
    data=observed().model_dump(mode="json")
    if case=="duration": data["scenes"][-1]["end_sec"]=35
    elif case=="count": data["scene_count"]=99
    else: data["avg_scene_sec"]=99
    result=StyleAnalysis.model_validate(data)
    assert result.normalization_notes and result.scene_count==len(result.scenes)
    assert result.scenes[-1].end_sec<=result.duration_sec+.5


def test_real_tin_tuc_2_raw_reparses_offline_without_changing_paid_raw(style_settings,monkeypatch):
    path=ROOT_DIR/"assets/reference_videos/analysis/tin-tuc/9e5386b8a856833a7c9e6133d6c0660a558409ceacbefce20bdbf7d21d4bceb0.raw.txt"
    if not path.exists():
        pytest.skip("Local regression raw not present in this checkout")
    original=path.read_bytes()
    video=style_settings.root_dir/"assets/reference_videos/tin-tuc/tin_tuc_2.mp4"
    video.parent.mkdir();video.write_bytes(b"regression reference")
    monkeypatch.setattr("pipeline.style_learner.inspect_video",lambda p,s:{"duration_sec":178.8,"size_bytes":p.stat().st_size})
    target=raw_path(style_settings,"tin-tuc",digest_file(video));target.parent.mkdir(parents=True)
    target.write_bytes(original)
    constructor=Mock(side_effect=AssertionError("No Gemini calls from raw"))
    monkeypatch.setattr("pipeline.style_learner.VideoStyleProvider",constructor)
    result=analyze_one(style_settings,"tin-tuc/tin_tuc_2.mp4",from_raw=True)
    assert len(result["analysis"]["scenes"])==13
    assert result["analysis"]["scenes"][-1]["transition_to_next"] is None
    assert result["analysis"]["duration_sec"]==178.8
    assert any("ngoài phạm vi" in w for w in result["warnings"])
    assert any("cắt end_sec" in w for w in result["warnings"])
    assert target.read_bytes()==original and path.read_bytes()==original
    constructor.assert_not_called()


def truncated_response():
    return types.GenerateContentResponse(candidates=[types.Candidate(finish_reason="MAX_TOKENS",
        content=types.Content(parts=[types.Part(text='{"scenes": [')]))])


def compact_response():
    return SimpleNamespace(candidates=[],prompt_feedback=None,text=json.dumps({"duration_sec":30,
        "scenes":[{"start_sec":"0","end_sec":"30","purpose":"giải thích","narration_summary":" ".join(["mô tả"]*30),"shot_count":"10","transition_to_next":None}],
        "reusable_rules":["Mỗi cảnh một ý"]},ensure_ascii=False))


def sdk(style_settings,monkeypatch,responses):
    client=Mock();client.models.generate_content.side_effect=responses
    client.files.upload.return_value=SimpleNamespace(name="files/mock",uri="https://example.com/mock",state=SimpleNamespace(name="ACTIVE"))
    monkeypatch.setattr("providers.llm_gemini.genai.Client",lambda **kw:client)
    settings=style_settings.model_copy(update={"style_request_interval_sec":0})
    return client,VideoStyleProvider(settings)


def test_max_tokens_retries_once_with_small_schema_and_keeps_truncated_archive(style_settings,monkeypatch):
    client,provider=sdk(style_settings,monkeypatch,[truncated_response(),compact_response()])
    result=analyze_one(style_settings,"a.mp4",provider=provider)
    calls=client.models.generate_content.call_args_list
    assert len(calls)==2
    assert all(c.kwargs["config"].max_output_tokens==8192 for c in calls)
    assert "CHẾ ĐỘ GỌN" in calls[1].kwargs["contents"][1]
    schema=calls[1].kwargs["config"].response_json_schema
    assert schema["properties"]["scenes"]["maxItems"]==12
    assert "captions" not in schema["properties"]
    assert len(result["analysis"]["scenes"][0]["narration_summary"].split())<=20
    target=raw_path(style_settings,None,digest_file(style_settings.root_dir/"assets/reference_videos/a.mp4"))
    metas=[json.loads(p.read_text(encoding="utf-8")) for p in target.parent.glob("*.raw.meta.json")]
    assert any(m.get("truncated") for m in metas)
    assert any(m.get("status",{}).get("mode")=="compact" and not m["truncated"] for m in metas)
    client.files.delete.assert_called_once()


def test_two_truncations_stop_and_next_run_does_not_keep_spending(style_settings,monkeypatch):
    from providers.llm_gemini import GeminiOutputError
    client,provider=sdk(style_settings,monkeypatch,[truncated_response(),truncated_response()])
    with pytest.raises(GeminiOutputError):
        analyze_one(style_settings,"a.mp4",provider=provider)
    assert client.models.generate_content.call_count==2
    constructor=Mock(side_effect=AssertionError("No third generation"))
    monkeypatch.setattr("pipeline.style_learner.VideoStyleProvider",constructor)
    with pytest.raises(StyleRawError):
        analyze_one(style_settings,"a.mp4")
    constructor.assert_not_called()
    client.files.delete.assert_called_once()


def test_existing_unbalanced_stop_raw_never_generates_or_changes_paid_output(style_settings,monkeypatch):
    file=style_settings.root_dir/"assets/reference_videos/a.mp4"
    store=RawResponse(raw_path(style_settings,None,digest_file(file)),{},style_diagnostics(style_settings))
    store.save('{"scenes": [',{"finish_reasons":["STOP"]})
    client,provider=sdk(style_settings,monkeypatch,[compact_response()])
    with pytest.raises(StyleRawError):
        analyze_one(style_settings,"a.mp4",provider=provider)
    client.models.generate_content.assert_not_called()
    client.files.upload.assert_not_called()
    assert store.path.read_text(encoding="utf-8")=='{"scenes": ['
    assert any(json.loads(p.read_text(encoding="utf-8")).get("truncated") for p in store.path.parent.glob("*.raw.meta.json"))


def test_stop_but_unbalanced_raw_marks_truncated_and_from_raw_never_calls(style_settings,monkeypatch):
    file=style_settings.root_dir/"assets/reference_videos/a.mp4"
    store=RawResponse(raw_path(style_settings,None,digest_file(file)),{},style_diagnostics(style_settings))
    store.save('{"scenes": [',{"finish_reasons":["STOP"]})
    constructor=Mock(side_effect=AssertionError("Offline parse must stay offline"))
    monkeypatch.setattr("pipeline.style_learner.VideoStyleProvider",constructor)
    result=analyze_batch(style_settings,["a.mp4"],from_raw=True)
    assert result[0]["status"]=="failed"
    assert store.metadata()["truncated"] and store.metadata()["status"]["finish_reasons"]==["STOP"]
    assert store.path.read_text(encoding="utf-8")=='{"scenes": ['
    constructor.assert_not_called()


def test_minimal_observations_still_build_category_profile(style_settings):
    from pipeline.category_style import rebuild_category
    video=style_settings.root_dir/"assets/reference_videos/tin-tuc/minimal.mp4"
    video.parent.mkdir();video.write_bytes(b"minimal")
    target=raw_path(style_settings,"tin-tuc",digest_file(video));target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"scenes":[{"start_sec":0,"end_sec":30,"purpose":"giải thích"}]}),encoding="utf-8")
    analyze_one(style_settings,"tin-tuc/minimal.mp4",from_raw=True)
    profile=rebuild_category(style_settings,"tin-tuc")
    assert profile.video_count==1 and profile.scene_pacing and profile.scene_patterns[0].shot_count is None


def test_motion_analysis_and_style_refinements():
    # 1. suggested_type accepts tutorial, explainer, review, news, story
    for stype in ("tutorial", "explainer", "review", "news", "story"):
        analysis = StyleAnalysis(scenes=[{"start_sec": 0, "end_sec": 10, "purpose": "hook"}], suggested_type=stype)
        assert analysis.suggested_type == stype

    # 2. words_per_sec and unit
    analysis = StyleAnalysis(
        scenes=[{"start_sec": 0, "end_sec": 10, "purpose": "hook", "words_per_sec": 3.2, "words_per_sec_unit": "từ/giây"}],
        narration_style={"words_per_sec": 3.5, "words_per_sec_unit": "âm tiết/giây"}
    )
    assert analysis.scenes[0].words_per_sec == 3.2
    assert analysis.scenes[0].words_per_sec_unit == "từ/giây"
    assert analysis.narration_style.words_per_sec == 3.5
    assert analysis.narration_style.words_per_sec_unit == "âm tiết/giây"

    # 3. captions.appearance: only "pill" if really pill, otherwise "classic"
    a_pill = StyleAnalysis(scenes=[{"start_sec": 0, "end_sec": 10, "purpose": "hook"}], captions={"appearance": "pill"})
    assert a_pill.captions.appearance == "pill"
    a_classic = StyleAnalysis(scenes=[{"start_sec": 0, "end_sec": 10, "purpose": "hook"}], captions={"appearance": "none"})
    assert a_classic.captions.appearance == "classic"
    a_plain = StyleAnalysis(scenes=[{"start_sec": 0, "end_sec": 10, "purpose": "hook"}], captions={"appearance": "classic"})
    assert a_plain.captions.appearance == "classic"

    # 4. motion_analysis full block
    m_data = {
        "world_type": "continuous_stage",
        "real_cuts_count": 0,
        "actors": [
            {"name": "laptop", "first_sec": 0.2, "last_sec": 6.5, "persistent_across_scenes": True, "states_seen": ["open", "typing"], "motions": ["enter", "type"]}
        ],
        "connectors": [
            {"from": "laptop", "to": "vps", "carries": "gói file", "start_sec": 1.8, "end_sec": 5.0}
        ],
        "hud": {
            "top_bar": "TECH EXPLAINER",
            "step_tracker": {"stations": 5, "labels": ["B1", "B2"], "marker_motion": "fill", "morphs_into": "road lúc giây 37.5"},
            "footer_note": "hình mô phỏng",
            "progress_dots": True
        },
        "text_layers": [
            {"role": "title", "position": "top", "size_rel": 0.08, "color": "#ffffff", "keyword_highlight": "SSH", "enter_anim": "fade"}
        ],
        "transitions_between_scenes": [
            {"at_sec": 6.5, "type": "none", "detail": "camera pan"}
        ],
        "camera": [
            {"at_sec": 0, "move": "zoom_in", "amount_rel": 0.05}
        ],
        "bookends": "laptop mở đầu và recap kết",
        "motion_events_per_10s": 4.5,
        "longest_static_sec": 0.4,
        "sfx_confidence": "heard"
    }
    analysis = StyleAnalysis(scenes=[{"start_sec": 0, "end_sec": 10, "purpose": "hook"}], motion_analysis=m_data)
    ma = analysis.motion_analysis
    assert ma.world_type == "continuous_stage"
    assert ma.real_cuts_count == 0
    assert len(ma.actors) == 1 and ma.actors[0].name == "laptop"
    assert len(ma.connectors) == 1 and ma.connectors[0].from_actor == "laptop" and ma.connectors[0].to_actor == "vps"
    assert ma.hud.step_tracker.stations == 5
    assert ma.hud.footer_note == "hình mô phỏng"
    assert len(ma.text_layers) == 1 and ma.text_layers[0].role == "title"
    assert len(ma.camera) == 1 and ma.camera[0].move == "zoom_in"
    assert ma.sfx_confidence == "heard"
    assert ma.longest_static_sec == 0.4
    assert ma.motion_events_per_10s == 4.5
