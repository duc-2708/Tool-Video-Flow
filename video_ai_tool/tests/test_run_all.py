"""Run-all coordination with real schemas/files and mocked stage functions only."""
import hashlib
import json
from pathlib import Path
from threading import Event
import pytest
from pydantic import SecretStr
from config.settings import Settings
from pipeline.run_all import RunConfig,run_all,saved_config,PipelineError,ApprovalRequired
from pipeline.assets import persist,source_hash
from agents.director import validate_plan,DirectorRequest,brief_hash
from schemas.edit_plan import EditPlan
from schemas.assets import ResolvedEditPlan,AssetsManifest,SceneAssets,ShotAsset
from tests.test_director import fixture_brief,fixture_plan
from utils.cache import write_json,cache_key
from utils.diagnostics import Diagnostics


@pytest.fixture
def stages(tmp_path,monkeypatch):
    import pipeline.run_all as module
    settings = Settings(root_dir=tmp_path,gemini_api_key=SecretStr("fixture-private"),gemini_model="fixture",
                        gateway_api_key=SecretStr("fixture-private-gateway"))
    calls,failures,inputs = [],{},{}
    brief = fixture_brief()
    brief.facts = [brief.facts[0].model_copy(deep=True) for _ in range(3)]
    def enter(step):
        calls.append(step)
        if failures.get(step,0):
            failures[step] -= 1
            raise RuntimeError("Lỗi fixture-private ở "+step)
    def research(topic,settings,**kwargs):
        enter("research")
        project = kwargs["output_dir"]
        data = brief.model_copy(update={"topic":topic})
        write_json(project/"brief.json",data.model_dump(mode="json"))
        write_json(project/"sources.json",{"sources":[{"url":"https://example.com/"}],"warnings":["Cảnh báo nguồn fixture"]})
        inputs["youtube"] = kwargs["use_youtube"]
        kwargs["progress"]("Nguồn web sẵn sàng")
        return project/"brief.json"
    def director(path,settings,**kwargs):
        enter("director")
        current = type(brief).model_validate_json(path.read_text(encoding="utf-8"))
        data = fixture_plan()
        data["voice"] = settings.default_voice
        plan = validate_plan(EditPlan.model_validate(data),current,
            DirectorRequest(video_type=kwargs["video_type"],video_format=kwargs["video_format"],duration_sec=kwargs["duration_sec"]))
        plan.video_type,plan.target_duration_sec,plan.brief_hash = kwargs["video_type"],kwargs["duration_sec"],brief_hash(current)
        write_json(path.parent/"edit_plan.json",plan.model_dump(mode="json"))
        return path.parent/"edit_plan.json"
    def assets(path,settings,**kwargs):
        enter("assets")
        plan = EditPlan.model_validate_json(path.read_text(encoding="utf-8"))
        project = path.parent
        rows = []
        for scene in plan.scenes:
            audio = f"audio/scene_{scene.id}.mp3"
            (project/audio).parent.mkdir(exist_ok=True)
            (project/audio).write_bytes(b"mock MP3 samples")
            shots = []
            for index,shot in enumerate(scene.shots,1):
                clip = f"clips/scene_{scene.id}_shot_{index}.png"
                (project/clip).parent.mkdir(exist_ok=True)
                (project/clip).write_bytes(b"mock image")
                shots.append(ShotAsset(shot_id=index,query=shot.query,media_type="color",path=clip,provider="generated",fallback=True))
            rows.append(SceneAssets(scene_id=scene.id,audio_path=audio,audio_duration_sec=scene.duration_sec,shots=shots))
        fingerprint = source_hash(plan)
        resolved = ResolvedEditPlan.model_validate({**plan.model_dump(mode="json"),"source_plan_hash":fingerprint,"timing_basis":"audio","warnings":["Fallback fixture"]})
        manifest = AssetsManifest(source_plan_hash=fingerprint,resolved_plan_hash=cache_key(resolved.model_dump(mode="json")),status="complete",scenes=rows,warnings=["Fallback fixture"])
        path = persist(project,resolved,manifest,Diagnostics(settings.logs_dir))
        inputs["original_resolved"] = (project/"edit_plan.resolved.json").read_bytes()
        inputs["original_manifest"] = path.read_bytes()
        return path
    def render(path,*,settings,mode,progress):
        enter("render")
        inputs["render_plan"] = path
        root = path.parent/"render"
        root.mkdir(exist_ok=True)
        output = root/f"fixture_{mode}.mp4"
        output.write_bytes(b"mock MP4 bytes")
        (root/"credits.txt").write_bytes((path.parent/"credits.txt").read_bytes())
        progress(1.,"Dựng xong")
        return {"path":str(output),"filename":output.name,"mode":mode,"duration_sec":45.,"width":540,"height":960,"fps":30,
                "size_bytes":output.stat().st_size,"render_seconds":1.,"warnings":[]}
    monkeypatch.setattr(module,"run_research",research)
    monkeypatch.setattr(module,"run_director",director)
    monkeypatch.setattr(module,"run_assets",assets)
    monkeypatch.setattr(module,"run_render",render)
    monkeypatch.setattr(module,"save_edit_plan",lambda path,data,settings:write_json(path.parent/"edit_plan.json",data))
    return settings,calls,failures,inputs


def state(project):
    return json.loads((project/"run_state.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("policy",["skip","stop","ask"])
def test_ai_failure_policy_keeps_broll_or_waits(stages,monkeypatch,policy):
    from unittest.mock import Mock
    settings,calls,_,inputs = stages
    ai = Mock(side_effect=RuntimeError("Job chưa có remote ID"))
    monkeypatch.setattr("pipeline.run_all.prepare_ai_bundle",ai)
    config = RunConfig(topic="Clip AI lỗi",ai_clips=1,ai_confirmed=True,ai_failure_action=policy)
    if policy == "stop":
        with pytest.raises(PipelineError,match="remote ID"):
            run_all(config,settings=settings)
        project = next(settings.output_dir.iterdir())
        assert "render" not in calls
        assert state(project)["status"] == "failed"
    else:
        project = run_all(config,settings=settings)
        assert state(project)["status"] == "done"
        assert state(project)["steps"]["ai_video"]["status"] == "skipped"
        assert "remote ID" in " ".join(state(project)["steps"]["ai_video"]["warnings"])
        assert "remote ID" in (project/"report.md").read_text(encoding="utf-8")
        assert Path(state(project)["render_result"]["path"]).is_file()
        assert inputs["render_plan"] == project/"edit_plan.resolved.json"
        # Resuming a completed fallback run must not retry a paid stage.
        run_all(saved_config(project),settings=settings)
    ai.assert_called_once()


def test_ai_failure_stop_decision_does_not_retry(stages,monkeypatch):
    from unittest.mock import Mock
    settings,calls,_,_ = stages
    ai = Mock(side_effect=RuntimeError("Job chưa có remote ID"))
    monkeypatch.setattr("pipeline.run_all.prepare_ai_bundle",ai)
    with pytest.raises(PipelineError):
        run_all(RunConfig(topic="Dừng AI",ai_clips=1,ai_confirmed=True,ai_failure_action="stop"),settings=settings)
    project = next(settings.output_dir.iterdir())
    run_all(saved_config(project,ai_failure_decision="stop"),settings=settings)
    assert state(project)["status"] == "failed"
    assert "remote ID" in state(project)["error"]
    assert "render" not in calls
    ai.assert_called_once()


def test_ai_fallback_still_respects_stop_after(stages,monkeypatch):
    from unittest.mock import Mock
    settings,calls,_,_ = stages
    monkeypatch.setattr("pipeline.run_all.prepare_ai_bundle",Mock(side_effect=RuntimeError("Missing ID fixture")))
    project = run_all(RunConfig(topic="Dừng sau AI",ai_clips=1,ai_confirmed=True),settings=settings,stop_after="ai_video")
    assert state(project)["status"] == "paused"
    assert state(project)["steps"]["ai_video"]["status"] == "skipped"
    assert "render" not in calls


def test_run_state_replace_denied_uses_direct_fallback(stages,monkeypatch):
    from utils import atomic_io
    settings,calls,_,_ = stages
    original = atomic_io.os.replace
    attempts = []
    def replace(source,target):
        if Path(target).name == "run_state.json":
            attempts.append(target)
            error = PermissionError("fixture locked state")
            error.winerror = 5
            raise error
        return original(source,target)
    monkeypatch.setattr(atomic_io.os,"replace",replace)
    monkeypatch.setattr(atomic_io.time,"sleep",lambda _:None)
    monkeypatch.setattr(atomic_io,"LOG_PATH",settings.logs_dir/"atomic_io.log")
    project = run_all(RunConfig(topic="Khóa trạng thái"),settings=settings)
    assert state(project)["status"] == "done"
    assert calls == ["research","director","assets","render"]
    assert len(attempts) >= 8 and len(attempts) % 8 == 0
    assert not list(project.rglob("*.tmp"))


def test_unwritable_status_does_not_fail_completed_stages(stages,monkeypatch):
    import pipeline.run_all as module
    settings,calls,_,_ = stages
    original = module.write_json
    events = []
    def write(path,data):
        if path.name == "run_state.json":
            raise PermissionError("fixture status file is unwritable")
        return original(path,data)
    monkeypatch.setattr(module,"write_json",write)
    project = run_all(RunConfig(topic="Trạng thái trong bộ nhớ"),progress_cb=events.append,settings=settings)
    assert calls == ["research","director","assets","render"]
    assert events[-1]["state"]["status"] == "done"
    assert "state_write_warning" in events[-1]["state"]
    assert (project/"report.md").is_file()


def test_order_default_ai_off_report_and_voice(stages,monkeypatch):
    settings,calls,failures,inputs = stages
    ai = __import__("unittest.mock",fromlist=["Mock"]).Mock(side_effect=AssertionError("AI mặc định không chạy"))
    monkeypatch.setattr("pipeline.run_all.prepare_ai_bundle",ai)
    updates = []
    project = run_all(RunConfig(topic="Video fixture",voice="vi-VN-NamMinhNeural",youtube_trends=True),updates.append,settings=settings)
    assert calls == ["research","director","assets","render"] and inputs["youtube"] is True
    result = state(project)
    assert result["status"] == "done" and result["steps"]["ai_video"]["status"] == "skipped"
    assert result["summary"]["facts"] == 3 and result["summary"]["facts_used"] == 1 and result["summary"]["sources_used"] == 1
    assert EditPlan.model_validate_json((project/"edit_plan.json").read_text(encoding="utf-8")).voice == "vi-VN-NamMinhNeural"
    assert (project/"render/credits.txt").exists() and (project/"report.md").exists()
    assert "https://example.com/" in (project/"report.md").read_text(encoding="utf-8")
    assert "Cảnh báo nguồn fixture" in (project/"report.md").read_text(encoding="utf-8")
    assert "fixture-private" not in (project/"run_state.json").read_text(encoding="utf-8")
    assert updates[-1]["state"]["status"] == "done"


def test_resume_after_failure_skips_done_steps(stages):
    settings,calls,failures,inputs = stages
    failures["assets"] = 1
    config = RunConfig(topic="Resume fixture")
    with pytest.raises(PipelineError,match="Assets"):
        run_all(config,settings=settings)
    project = next(settings.output_dir.iterdir())
    first = state(project)
    assert first["steps"]["director"]["status"] == "done" and first["steps"]["assets"]["status"] == "failed"
    assert "fixture-private" not in first["error"]
    result = run_all(saved_config(project),settings=settings)
    assert result == project and calls == ["research","director","assets","assets","render"]
    assert state(project)["steps"]["assets"]["attempts"] == 2
    calls.clear()
    run_all(saved_config(project),settings=settings)
    assert not calls


def test_review_stops_then_accepts_edited_plan_and_continues(stages):
    settings,calls,failures,inputs = stages
    project = run_all(RunConfig(topic="Review fixture",mode="review"),settings=settings)
    assert calls == ["research","director"] and state(project)["status"] == "waiting_review"
    data = json.loads((project/"edit_plan.json").read_text(encoding="utf-8"))
    data["scenes"][1]["narration"] = "Theo example.com, Có thể ghép video rồi cắt video."
    write_json(project/"edit_plan.json",data)
    run_all(saved_config(project,continue_after_review=True),settings=settings)
    assert calls == ["research","director","assets","render"]
    assert state(project)["review_approved"] is True and state(project)["status"] == "done"
    assert json.loads((project/"edit_plan.json").read_text(encoding="utf-8"))["scenes"][1]["narration"] == data["scenes"][1]["narration"]


def test_new_and_force_runs_never_overwrite_old_project(stages):
    settings,calls,failures,inputs = stages
    config = RunConfig(topic="Cùng chủ đề")
    first = run_all(config,settings=settings)
    original = {str(path.relative_to(first)):hashlib.sha256(path.read_bytes()).hexdigest() for path in first.rglob("*") if path.is_file()}
    second = run_all(config,settings=settings)
    third = run_all(saved_config(first,force=True),settings=settings)
    assert len({first,second,third}) == 3
    assert original == {str(path.relative_to(first)):hashlib.sha256(path.read_bytes()).hexdigest() for path in first.rglob("*") if path.is_file()}


def test_ai_requires_confirmation_before_any_step_or_project(stages):
    settings,calls,failures,inputs = stages
    with pytest.raises(ApprovalRequired,match="Sẽ tạo 1 clip, model veo-3.1, thời lượng 4"):
        run_all(RunConfig(topic="AI fixture",ai_clips=1),settings=settings)
    assert not calls and not settings.output_dir.exists()
    with pytest.raises(ValueError,match="AI_CLIP_MAX_PER_RUN"):
        run_all(RunConfig(topic="AI fixture",ai_clips=4,ai_confirmed=True),settings=settings)
    assert not calls


def test_ai_clips_are_used_in_separate_bundle_and_original_assets_unchanged(stages,monkeypatch):
    import pipeline.run_all_ai as ai
    settings,calls,failures,inputs = stages
    requests = []
    def create(project,request,settings):
        calls.append("ai_create")
        requests.append(request)
        path = project/"ai_video/job.json"
        write_json(path,{"request":request.model_dump(mode="json"),"remote_id":"fixture_remote"})
        return path
    def resume(path,settings,**kwargs):
        calls.append("ai_resume")
        clip = path.parent.parent/"clips/fixture_ai.mp4"
        clip.write_bytes(b"mock generated MP4")
        return {"remote_id":"fixture_remote","clip_path":"clips/fixture_ai.mp4","duration_sec":4.,"actual_cost_vnd":"2500"}
    monkeypatch.setattr(ai,"create_job",create)
    monkeypatch.setattr(ai,"resume_job",resume)
    # Explicit legacy bundle regression; the default Motion3 mode is a backdrop.
    project = run_all(RunConfig(topic="AI fixture",ai_clips=1,ai_confirmed=True,ai_background_only=False),settings=settings)
    assert calls == ["research","director","assets","ai_create","ai_resume","render"]
    assert len(requests) == 1 and requests[0].seconds == 4
    assert inputs["render_plan"].parent == project/"ai_render"
    resolved = ResolvedEditPlan.model_validate_json(inputs["render_plan"].read_text(encoding="utf-8"))
    assert resolved.scenes[0].shots[0].type == "ai_video"
    assert (project/"edit_plan.resolved.json").read_bytes() == inputs["original_resolved"]
    assert (project/"assets.json").read_bytes() == inputs["original_manifest"]
    assert state(project)["ai_clips_used"][0]["remote_id"] == "fixture_remote"
    assert "AI-generated" in (project/"render/credits.txt").read_text(encoding="utf-8")
    assert Path(state(project)["render_result"]["path"]).parent == project/"render"


def test_partial_assets_stop_before_render(stages,monkeypatch):
    import pipeline.run_all as module
    settings,calls,failures,inputs = stages
    original = module.run_assets
    def partial(*args,**kwargs):
        path = original(*args,**kwargs)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = "partial"
        write_json(path,data)
        return path
    monkeypatch.setattr(module,"run_assets",partial)
    with pytest.raises(PipelineError,match="Assets chưa hoàn tất"):
        run_all(RunConfig(topic="Partial"),settings=settings)
    assert "render" not in calls


def test_modified_completed_artifact_is_not_silently_used(stages):
    settings,calls,failures,inputs = stages
    project = run_all(RunConfig(topic="Checksum"),settings=settings)
    (project/"audio/scene_1.mp3").write_bytes(b"tampered fixture")
    calls.clear()
    with pytest.raises(PipelineError,match="Artifact của bước Assets đã đổi"):
        run_all(saved_config(project),settings=settings)
    assert not calls


def test_cooperative_cancel_and_resume(stages):
    settings,calls,failures,inputs = stages
    event = Event()
    def progress(update):
        if update["step"] == "research" and update["state"]["steps"]["research"]["status"] == "done":
            event.set()
    project = run_all(RunConfig(topic="Cancel"),progress,settings=settings,cancel_event=event)
    assert state(project)["status"] == "cancelled" and calls == ["research"]
    event.clear()
    run_all(saved_config(project),settings=settings,cancel_event=event)
    assert calls == ["research","director","assets","render"]


def test_stop_after_and_config_change_guard(stages):
    settings,calls,failures,inputs = stages
    project = run_all(RunConfig(topic="Stop after"),stop_after="director",settings=settings)
    assert state(project)["status"] == "paused" and calls == ["research","director"]
    with pytest.raises(ValueError,match="Cấu hình khác"):
        run_all(saved_config(project,topic="Different"),settings=settings)
    run_all(saved_config(project),settings=settings)
    assert state(project)["status"] == "done"


def test_python_config_aliases_and_default_voice(stages):
    settings,calls,failures,inputs = stages
    settings = settings.model_copy(update={"default_voice":"vi-VN-NamMinhNeural"})
    project = run_all({"topic":"Config aliases","type":"news","format":"tiktok","duration":45},settings=settings)
    assert state(project)["config"]["voice"] == "vi-VN-NamMinhNeural"


def test_cli_requires_ai_confirmation_without_starting_stages(stages,monkeypatch,capsys):
    import pipeline.run_all as module
    settings,calls,failures,inputs = stages
    monkeypatch.setattr(module,"get_settings",lambda:settings)
    monkeypatch.setattr("sys.argv",["run_all","--topic","CLI","--ai-clips","1"])
    assert module.main() == 2
    assert not calls and "Sẽ tạo 1 clip" in capsys.readouterr().out


def test_done_ai_stage_can_resume_render_without_gateway_key(stages,monkeypatch):
    settings,calls,failures,inputs = stages
    def ai(project,config,settings,progress,check_cancel,diagnostics):
        calls.append("ai")
        return project/"edit_plan.resolved.json",[]
    monkeypatch.setattr("pipeline.run_all.prepare_ai_bundle",ai)
    failures["render"] = 1
    with pytest.raises(PipelineError,match="Render"):
        run_all(RunConfig(topic="Resume render only",ai_clips=1,ai_confirmed=True),settings=settings)
    project = next(settings.output_dir.iterdir())
    assert state(project)["steps"]["ai_video"]["status"] == "done"
    settings = settings.model_copy(update={"gateway_api_key":SecretStr(""),"ai_clip_max_per_run":0})
    run_all(saved_config(project),settings=settings)
    assert calls.count("ai") == 1 and state(project)["status"] == "done"


def test_ai_expanded_resolved_shots_lookup_and_warn_without_touching_originals(stages, monkeypatch):
    from pipeline.assets import load_assets
    import pipeline.run_all_ai as ai
    settings, calls, _, _ = stages
    project = run_all(RunConfig(topic="Expanded resolved"), settings=settings, stop_after="assets")
    original, resolved, manifest = load_assets(project/"edit_plan.json")
    scene = resolved.scenes[1]
    row = next(s for s in manifest.scenes if s.scene_id == scene.id)
    next_id = len(scene.shots) + 1
    scene.shots.append(scene.shots[0].model_copy(deep=True))
    row.shots.append(row.shots[0].model_copy(update={"shot_id": next_id}, deep=True))
    row.audio_duration_sec = scene.duration_sec
    for item in manifest.scenes:
        for shot in item.shots:
            shot.fallback = item.scene_id == scene.id and shot.shot_id == next_id
    persist(project, resolved, manifest, Diagnostics(settings.logs_dir))
    before = {name: (project/name).read_bytes() for name in ["edit_plan.json", "edit_plan.resolved.json", "assets.json"]}
    def create(project, request, settings):
        path = project/"ai_video/test.json"
        write_json(path, {"remote_id": "fixture"})
        return path
    def resume(path, settings, **kwargs):
        (project/"clips/ai.mp4").write_bytes(b"mock AI")
        return {"remote_id": "fixture", "clip_path": "clips/ai.mp4", "duration_sec": 4.}
    monkeypatch.setattr(ai, "create_job", create)
    monkeypatch.setattr(ai, "resume_job", resume)
    bundle, used = ai.prepare_ai_bundle(project, RunConfig(topic="Expanded", ai_clips=1,ai_background_only=False), settings,
        lambda *args: None, lambda: None, Diagnostics(settings.logs_dir, filename="run_all_errors.log"))
    assert used[0]["scene_id"] == scene.id and used[0]["shot_id"] == next_id
    assert bundle.is_file()
    assert "Không tìm thấy shot gốc" in (settings.logs_dir/"run_all_errors.log").read_text(encoding="utf-8")
    assert all((project/name).read_bytes() == data for name, data in before.items())
    assert any("Không tìm thấy shot gốc" in warning for warning in json.loads((bundle.parent/"assets.json").read_text(encoding="utf-8"))["warnings"])


def test_unavailable_ai_model_falls_back_and_reports(stages, monkeypatch):
    from unittest.mock import Mock
    settings, calls, _, inputs = stages
    gateway = Mock()
    monkeypatch.setattr("pipeline.run_all.prepare_ai_bundle", gateway)
    project = run_all(RunConfig(topic="Model forbidden", ai_clips=1, ai_confirmed=True,
        ai_model="seedance-2.5", ai_seconds=30), settings=settings)
    assert state(project)["status"] == "done"
    assert state(project)["steps"]["ai_video"]["status"] == "skipped"
    assert "GATEWAY_ALLOWED_MODELS" in (project/"report.md").read_text(encoding="utf-8")
    assert inputs["render_plan"] == project/"edit_plan.resolved.json"
    gateway.assert_not_called()


def test_refresh_shot_uses_manifest_ids_instead_of_order(stages, monkeypatch):
    from pipeline.assets import load_assets, refresh_shot
    settings, _, _, _ = stages
    project = run_all(RunConfig(topic="Manifest order"), settings=settings, stop_after="assets")
    _, resolved, manifest = load_assets(project/"edit_plan.json")
    row = next(s for s in manifest.scenes if len(s.shots) >= 2)
    row.shots.reverse()
    untouched = next(s for s in row.shots if s.shot_id == 2).model_dump()
    persist(project, resolved, manifest, Diagnostics(settings.logs_dir))
    def stock(shot, scene_id, shot_id, *args, **kwargs):
        return next(s for s in row.shots if s.shot_id == shot_id).model_copy(update={"query": shot.query})
    monkeypatch.setattr("pipeline.assets.resolve_stock", stock)
    refresh_shot(project/"edit_plan.json", settings, row.scene_id, 1, "rocket launch", providers=[])
    _, _, updated = load_assets(project/"edit_plan.json")
    changed = next(s for s in updated.scenes if s.scene_id == row.scene_id)
    assert next(s for s in changed.shots if s.shot_id == 1).query == "rocket launch"
    assert next(s for s in changed.shots if s.shot_id == 2).model_dump() == untouched
    with pytest.raises(ValueError, match="Không tìm thấy"):
        refresh_shot(project/"edit_plan.json", settings, row.scene_id, 999, "none", providers=[])


def test_generation_failed_twice_still_renders_broll(stages, monkeypatch):
    from unittest.mock import Mock
    settings, calls, _, inputs = stages
    gateway = Mock()
    gateway.create.side_effect = [({"id":"failed_first"},None),({"id":"failed_retry"},None)]
    gateway.status.return_value = {"status":"failed","error":{"code":"generation_failed","message":"Upstream generation failed"}}
    monkeypatch.setattr("pipeline.ai_video.VideoGateway",lambda *args:gateway)
    project = run_all(RunConfig(topic="AI failure fallback",ai_clips=1,ai_confirmed=True,ai_background_only=False),settings=settings)
    assert gateway.create.call_count == 2
    gateway.download.assert_not_called()
    assert state(project)["status"] == "done" and state(project)["steps"]["ai_video"]["status"] == "skipped"
    assert inputs["render_plan"] == project/"edit_plan.resolved.json"
    assert Path(state(project)["render_result"]["path"]).is_file()
    assert "generation_failed" in (project/"report.md").read_text(encoding="utf-8")


def test_run_all_uses_gateway_duration_defaults_from_settings(stages):
    settings, _, _, _ = stages
    settings = settings.model_copy(update={"gateway_video_model":"seedance-2.5-30s","ai_clip_seconds":10})
    project = run_all(RunConfig(topic="Settings defaults"),settings=settings)
    assert state(project)["config"]["ai_model"] == "seedance-2.5-30s"
    assert state(project)["config"]["ai_seconds"] == 10


def test_motion3_default_ai_is_background_and_failure_keeps_cards(stages,monkeypatch):
    settings,calls,_,inputs=stages
    settings=settings.model_copy(update={'motion_enabled':True})
    def backgrounds(project,settings,**kwargs):
        calls.append('ai_background')
        assert kwargs['confirmed'] and kwargs['count']==1
        result={'clips':[],'warnings':['Fixture generation_failed; dùng gradient.']}
        write_json(project/'render/ai_backgrounds.json',result)
        return result
    monkeypatch.setattr('pipeline.controlled_ai.create_backgrounds',backgrounds)
    project=run_all(RunConfig(topic='Controlled AI',ai_clips=1,ai_confirmed=True),settings=settings)
    assert calls==['research','director','assets','ai_background','render']
    assert inputs['render_plan']==project/'edit_plan.resolved.json'
    assert (project/'edit_plan.resolved.json').read_bytes()==inputs['original_resolved']
    assert 'generation_failed' in (project/'report.md').read_text(encoding='utf-8')
    assert state(project)['status']=='done'
