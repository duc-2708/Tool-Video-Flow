# file: tests/test_streamlit_ui.py
"""Kiểm tra UI bằng AppTest; không mạng, không key thật, không subprocess."""
from pathlib import Path
import pytest
from pydantic import SecretStr
from streamlit.testing.v1 import AppTest
from config.settings import ROOT_DIR, Settings
from pipeline.projects import create_project, list_projects, project_path
from providers.llm_base import ProviderError
from utils.cache import write_json


@pytest.fixture
def ui_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = Settings(root_dir=tmp_path, gemini_api_key=SecretStr("fixture-ui-private-key"), gemini_model="fixture-model")
    monkeypatch.setattr("config.settings.get_settings", lambda: settings)
    return settings


def brief_data(topic: str) -> dict:
    return {"topic": topic, "language": "vi", "angle_candidates": [{"angle": "Góc fixture", "why": "Dữ liệu kiểm thử"}],
            "facts": [{"claim": "Fixture cho UI", "source_name": "example.com", "source_url": "https://example.com",
                       "confidence": "low", "evidence_quote": "Fixture kiểm thử"}], "trends": [], "hooks": ["Hook fixture"],
            "audience_questions": ["Câu hỏi fixture"], "keywords": ["fixture"], "risks": ["Chỉ là dữ liệu kiểm thử"]}


def open_app() -> AppTest:
    app = AppTest.from_file(ROOT_DIR / "app/streamlit_app.py", default_timeout=20).run()
    return app.sidebar.radio[0].set_value("Research").run()


def button(at: AppTest, label: str):
    return next(item for item in at.button if item.label == label)


def test_project_reader_and_brief_tabs(ui_settings: Settings) -> None:
    project = create_project(ui_settings.output_dir, "Project fixture")
    write_json(project / "brief.json", brief_data("Project fixture"))
    write_json(project / "sources.json", {"sources": [], "warnings": []})
    at = open_app()
    assert not at.exception
    assert [tab.label for tab in at.tabs] == ["Research Brief", "Nguồn đối chiếu", "JSON thô"]
    assert len(at.dataframe) == 2
    assert at.dataframe[0].value.iloc[0]["source_url"] == "https://example.com/"
    status = "\n".join(item.value for item in at.sidebar.text)
    assert "GEMINI_API_KEY: Đã có" in status and "PEXELS_API_KEY: Chưa có" in status
    assert "Model: fixture-model" in status and "fixture-ui-private-key" not in status
    assert at.get("download_button")[0].proto.label == "Tải brief.json"
    button(at, "Project mới").click().run()
    assert not at.exception
    assert at.text_input[0].value == ""
    assert not at.tabs


def test_research_shows_kept_discarded_and_trimmed_counts(ui_settings: Settings) -> None:
    project = create_project(ui_settings.output_dir, "Project thống kê fact")
    data = brief_data("Project thống kê fact")
    data["facts"] = data["facts"] * 3
    write_json(project / "brief.json", data)
    write_json(project / "sources.json", {"sources": [], "warnings": ["Đã loại fact #5: quote không có trong nguồn."],
        "grounding": {"returned": 5, "kept": 3, "discarded": 2, "trimmed": 1}})
    at = open_app()
    assert not at.exception
    metrics = {item.label: item.value for item in at.metric}
    assert metrics["Fact giữ lại"] == "3"
    assert metrics["Fact bị loại"] == "2"
    assert metrics["Quote được rút gọn"] == "1"


def test_research_old_project_does_not_invent_discard_counts(ui_settings: Settings) -> None:
    project = create_project(ui_settings.output_dir, "Project cũ")
    write_json(project / "brief.json", brief_data("Project cũ"))
    at = open_app()
    assert not at.exception
    metrics = {item.label: item.value for item in at.metric}
    assert metrics["Fact bị loại"] == "—"


def test_research_displays_youtube_signals_separately_and_toggle(ui_settings: Settings, monkeypatch) -> None:
    from tests.test_youtube_trends import signal_fixture, insight_fixture
    project = create_project(ui_settings.output_dir, "Project YouTube trends")
    data = brief_data("Project YouTube trends")
    data.update(trend_signals=[signal_fixture().model_dump(mode="json")], trend_insights=insight_fixture())
    write_json(project / "brief.json", data)
    write_json(project / "sources.json", {"sources": [], "warnings": []})
    at = open_app()
    assert not at.exception
    assert any("views" in frame.value.columns and list(frame.value["views"]) == [100] for frame in at.dataframe)
    assert any("Mở bằng câu hỏi bắt đầu từ đâu" in item.value for item in at.markdown)
    assert any("Lý do:" in item.value for item in at.caption)
    assert any(item.label == "Bật YouTube trends" for item in at.checkbox)
    calls = []
    def research(topic,settings,**kwargs):
        calls.append((kwargs["use_youtube"], kwargs["youtube_days"], kwargs["youtube_vietnamese"]))
        return project / "brief.json"
    monkeypatch.setattr("app.views.research.run_research",research)
    next(widget for widget in at.checkbox if widget.label == "Bật YouTube trends").check()
    next(widget for widget in at.number_input if widget.label == "YouTube trends: số ngày gần đây").set_value(7)
    button(at,"Chạy Researcher").click().run()
    assert not at.exception and calls == [(True,7,True)]


def test_submit_uses_shared_research_and_reselects_new_project(ui_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    def fake_research(topic: str, settings: Settings, **kwargs) -> Path:
        calls.append((topic, kwargs["web_limit"], kwargs["use_youtube"]))
        project = kwargs["output_dir"]
        kwargs["progress"]("Đang kiểm tra fixture")
        write_json(project / "brief.json", brief_data(topic))
        write_json(project / "sources.json", {"sources": [], "warnings": []})
        return project / "brief.json"
    monkeypatch.setattr("app.views.research.run_research", fake_research)
    at = open_app()
    at.text_input[0].set_value("Chủ đề fixture")
    at.number_input[0].set_value(4)
    button(at, "Chạy Researcher").click().run()
    assert not at.exception
    assert calls == [("Chủ đề fixture", 4, False)]
    assert len(list_projects(ui_settings.output_dir)) == 1
    assert at.tabs and at.success
    assert at.selectbox[0].value != "__new_project__"
    # Tương tác đọc/tải không được gọi pipeline lại.
    at.checkbox(key="ui_debug").check().run()
    assert len(calls) == 1


def test_debug_root_error_is_visible_and_key_is_redacted(ui_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    def failed_research(*args, **kwargs):
        try:
            raise ValueError("Lỗi fixture gốc fixture-ui-private-key")
        except ValueError:
            raise ProviderError("Pipeline không hoàn tất") from None
    monkeypatch.setattr("app.views.research.run_research", failed_research)
    at = open_app()
    at.text_input[0].set_value("Fixture thất bại")
    button(at, "Chạy Researcher").click().run()
    assert not at.exception and at.error
    assert "ValueError" in at.error[0].value and "[REDACTED]" in at.error[0].value
    assert "fixture-ui-private-key" not in at.error[0].value
    assert not at.expander
    at.checkbox(key="ui_debug").check().run()
    assert not at.exception
    assert any("Traceback" in item.label for item in at.expander)
    assert "ValueError" in at.code[0].value and "fixture-ui-private-key" not in at.code[0].value
    saved = (ui_settings.logs_dir / "researcher_errors.log").read_text(encoding="utf-8")
    assert "fixture-ui-private-key" not in saved
    assert len(list_projects(ui_settings.output_dir)) == 1


def test_corrupt_project_does_not_crash_sidebar(ui_settings: Settings) -> None:
    project = create_project(ui_settings.output_dir, "Fixture lỗi JSON")
    (project / "brief.json").write_text("not json", encoding="utf-8")
    at = open_app()
    assert not at.exception and at.error


def test_project_path_cannot_escape_output(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        project_path(tmp_path / "output", "../outside")
    first = create_project(tmp_path / "output", "Cùng chủ đề")
    second = create_project(tmp_path / "output", "Cùng chủ đề")
    assert first != second


def test_director_page_generation_and_narration_save(ui_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.test_director import fixture_brief, fixture_plan
    from agents.director import brief_hash
    project = create_project(ui_settings.output_dir, "Director fixture")
    write_json(project / "brief.json", fixture_brief().model_dump(mode="json"))
    calls = []
    def fake_director(path: Path, settings: Settings, **kwargs) -> Path:
        calls.append(("generate", kwargs["video_type"], kwargs["video_format"], kwargs["duration_sec"]))
        data = fixture_plan()
        data.update(video_type="review", target_duration_sec=45.0, brief_hash=brief_hash(fixture_brief()))
        write_json(project / "edit_plan.json", data)
        return project / "edit_plan.json"
    def fake_save(path: Path, data: dict, settings: Settings) -> Path:
        calls.append(("save", data["scenes"][1]["narration"], data["scenes"][1]["shots"][0]["query"]))
        write_json(project / "edit_plan.json", data)
        return project / "edit_plan.json"
    monkeypatch.setattr("app.views.edit_plan.run_director", fake_director)
    monkeypatch.setattr("app.views.edit_plan.save_edit_plan", fake_save)
    at = open_app()
    at.radio[0].set_value("Edit Plan").run()
    assert not at.exception
    button(at, "Tạo Edit Plan").click().run()
    assert not at.exception and len(at.text_area) == 8
    assert calls[0] == ("generate", "review", "tiktok", 45.0)
    assert at.metric[0].value == "45.0 giây"
    from schemas.edit_plan import EditPlan
    from pipeline.projects import read_json
    from utils.cache import cache_key
    revision = cache_key(EditPlan.model_validate(read_json(project / "edit_plan.json")).model_dump(mode="json"))[:12]
    editor_key = f"shots_{project.name}_{revision}_2"
    at.session_state[editor_key] = {"edited_rows": {0: {"query": "editing software"}}, "added_rows": [], "deleted_rows": []}
    at.text_area[1].set_value("Lời đọc fixture đã chỉnh.")
    button(at, "Lưu chỉnh sửa").click().run()
    assert not at.exception
    assert calls[-1] == ("save", "Lời đọc fixture đã chỉnh.", "editing software")
    assert at.text_area[1].value == "Lời đọc fixture đã chỉnh."


def test_director_requires_brief(ui_settings: Settings) -> None:
    at = open_app()
    at.radio[0].set_value("Edit Plan").run()
    assert not at.exception
    assert not any(item.label == "Tạo Edit Plan" for item in at.button)


def test_director_review_notes_visible_only_as_editor_metadata(ui_settings: Settings) -> None:
    from tests.test_director import fixture_brief, fixture_plan
    from agents.director import DirectorRequest, validate_plan
    from schemas.edit_plan import EditPlan
    brief = fixture_brief()
    brief.facts[0].confidence = "low"
    project = create_project(ui_settings.output_dir, "Director nguồn")
    write_json(project / "brief.json", brief.model_dump(mode="json"))
    plan = validate_plan(EditPlan.model_validate(fixture_plan()), brief,
                         DirectorRequest(video_type="review", video_format="tiktok", duration_sec=45.))
    write_json(project / "edit_plan.json", plan.model_dump(mode="json"))
    at = open_app()
    at.radio[0].set_value("Edit Plan").run()
    assert not at.exception
    assert any("1 nguồn" in item.value for item in at.markdown)
    assert any("Ghi chú kiểm chứng" in item.value for item in at.markdown)
    assert any("Confidence: low" in item.value for item in at.caption)
    assert any("source_url" in frame.value.columns and "https://example.com/" in list(frame.value["source_url"]) for frame in at.dataframe)
    assert all("chưa xác minh" not in item.value.casefold() for item in at.text_area)


def test_assets_ui_calls_shared_pipeline_previews_and_refreshes_one_shot(ui_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil
    import subprocess
    from imageio_ffmpeg import get_ffmpeg_exe
    from providers.tts_edge import audio_duration
    from tests.test_director import fixture_plan
    from pipeline.assets import run_assets as backend_assets, refresh_shot as backend_refresh, load_assets
    project = create_project(ui_settings.output_dir, "Assets fixture")
    plan_path = project / "edit_plan.json"
    write_json(plan_path, fixture_plan())
    sample = ui_settings.root_dir / "fixture.mp3"
    subprocess.run([get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=2", str(sample)], capture_output=True, check=True, timeout=20)
    calls = []
    class FakeTTS:
        def synthesize(self, text, voice, destination):
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(sample, destination)
            return audio_duration(destination)
    def run(path, settings, **kwargs):
        calls.append("run")
        return backend_assets(path, settings, tts=FakeTTS(), providers=[], **kwargs)
    def refresh(path, settings, scene_id, shot_id, query):
        calls.append((scene_id, shot_id, query))
        return backend_refresh(path, settings, scene_id, shot_id, query, providers=[])
    monkeypatch.setattr("app.views.assets.run_assets", run)
    monkeypatch.setattr("app.views.assets.refresh_shot", refresh)
    at = open_app()
    at.radio[0].set_value("Assets").run()
    button(at, "Tạo Assets").click().run()
    assert not at.exception
    assert len(at.get("audio")) == 1 and len(at.image) == 1
    assert any("FALLBACK" in item.label for item in at.expander)
    _, _, before = load_assets(plan_path)
    previous_audio = (project / before.scenes[0].audio_path).read_bytes()
    at.text_input[0].set_value("editing software")
    button(at, "Tìm lại clip cho shot này").click().run()
    assert not at.exception and calls == ["run", (1, 1, "editing software")]
    _, _, after = load_assets(plan_path)
    assert after.scenes[0].shots[0].query == "editing software"
    assert (project / after.scenes[0].audio_path).read_bytes() == previous_audio
    plan_path.write_text(plan_path.read_text(encoding="utf-8").replace('"title": "Dựng video"', '"title": "Changed"'), encoding="utf-8")
    at.run()
    assert not at.exception and at.error
