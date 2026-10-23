"""Official API and Gemini are mocked. Never download a video or spend quota."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
import requests
from pydantic import SecretStr
from config.settings import ROOT_DIR,Settings
from db.repository import Repository
from pipeline.scan_sources import (add_source,preview_scan,learn_selected,estimate_selection,retry_candidates,main)
from pipeline.category_style import rebuild_category
from sources.youtube_resolver import YouTubeCatalog,resolve_source
from sources.youtube import QuotaExceeded
from tests.test_style_learner import observed

CHANNEL="UC"+"a"*22
IDS=[f"scanvid{i:04d}" for i in range(20)]
NOW=datetime(2026,10,22,12,tzinfo=timezone.utc)


@pytest.fixture
def cfg(tmp_path,monkeypatch):
    settings=Settings(root_dir=tmp_path,gemini_model="mock-style",gemini_api_key=SecretStr("fixture-scan-gemini-secret"),
        youtube_api_key=SecretStr("fixture-scan-youtube-secret"),retry_attempts=1)
    settings.prompts_dir.mkdir()
    (settings.prompts_dir/"style_analyze.md").write_text((ROOT_DIR/"prompts/style_analyze.md").read_text(encoding="utf-8"),encoding="utf-8")
    monkeypatch.setattr("pipeline.style_learner.inspect_video",lambda p,s:{"duration_sec":30.,"size_bytes":p.stat().st_size})
    return settings


def source(cfg,kind="channel"):
    return add_source(cfg,"công nghệ",{"kind":kind,"value":CHANNEL if kind=="channel" else "technology","label":"Kênh mock","source_url":"https://www.youtube.com/channel/"+CHANNEL,"thumbnail_url":""})


def detail(index,seconds=30,age=2,**status):
    return {"id":IDS[index],"snippet":{"title":"Video mock "+str(index),"channelId":CHANNEL,"publishedAt":(NOW-timedelta(days=age,minutes=index)).isoformat()},
        "statistics":{"viewCount":"1234"},"contentDetails":{"duration":f"PT{seconds}S"},"status":{"privacyStatus":"public","uploadStatus":"processed",**status}}


class Catalog:
    def __init__(self,items,pages=None):
        self.items={i["id"]:i for i in items}
        self.pages=pages or [list(self.items)]
        self.calls=[]

    def request(self,endpoint,params,**kwargs):
        self.calls.append((endpoint,params,kwargs))
        if endpoint=="channels":
            return {"items":[{"id":CHANNEL,"contentDetails":{"relatedPlaylists":{"uploads":"UUfixture"}}}]}
        if endpoint=="playlistItems":
            index=int(params.get("pageToken",0))
            raw={"items":[{"contentDetails":{"videoId":vid}} for vid in self.pages[index]]}
            if index+1<len(self.pages):
                raw["nextPageToken"]=str(index+1)
            return raw
        if endpoint=="search":
            return {"items":[{"id":{"videoId":vid}} for vid in self.items]}
        if endpoint=="videos":
            return {"items":[self.items[vid] for vid in params["id"].split(",") if vid in self.items]}
        raise AssertionError("No page scraping, video downloads or unofficial endpoints")


def ready(index=0):
    item=detail(index)
    return {"platform":"youtube","video_id":IDS[index],"title":item["snippet"]["title"],"url":"https://www.youtube.com/watch?v="+IDS[index],
        "channel_id":CHANNEL,"published_at":item["snippet"]["publishedAt"],"duration_sec":30.,"source_ids":[],"decision":"ready","reason":""}


@pytest.mark.parametrize("value,endpoint,field",[
    ("https://www.youtube.com/watch?v="+IDS[0],"videos","id"),
    ("https://youtu.be/"+IDS[0]+"?si=x","videos","id"),
    ("https://www.youtube.com/shorts/"+IDS[0],"videos","id"),
    ("https://www.youtube.com/@mockchannel/videos","channels","forHandle"),
    ("https://www.youtube.com/channel/"+CHANNEL,"channels","id"),
    ("https://www.youtube.com/playlist?list=PLfixture12345","playlists","id"),
])
def test_resolver_link_forms(value,endpoint,field):
    api=Mock()
    api.request.return_value={"items":[{"id":CHANNEL,"snippet":{"channelId":CHANNEL,"channelTitle":"Mock channel","title":"Mock title"}}]}
    result=resolve_source(value,api)
    assert result["choices"][0]["value"]==CHANNEL and not result["requires_selection"]
    assert api.request.call_args.args[0]==endpoint and field in api.request.call_args.args[1]
    assert api.request.call_count==1


def test_resolver_channel_name_requires_selection_and_keyword_never_searches():
    api=Mock()
    api.request.return_value={"items":[{"id":{"channelId":CHANNEL},"snippet":{"title":"Kênh fixture"}}]}
    result=resolve_source("Tên kênh",api)
    assert result["requires_selection"] and api.request.call_args.args[1]["type"]=="channel"
    api.reset_mock()
    assert resolve_source("Tên từ khóa",api,kind="keyword")["choices"][0]["kind"]=="keyword"
    api.request.assert_not_called()


@pytest.mark.parametrize("url",["https://tiktok.com/@mock","https://youtube.com.evil.test/watch?v="+IDS[0],"http://youtube.com/@mock","https://facebook.com/video/123"])
def test_other_platforms_and_unsafe_hosts_rejected(url):
    api=Mock()
    with pytest.raises(ValueError):
        resolve_source(url,api)
    api.request.assert_not_called()


def test_repository_unique_wal_threaded_and_short_connections(cfg):
    repo=Repository.for_settings(cfg)
    src=source(cfg)
    with ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(lambda i:repo.save_video("cong-nghe","youtube",IDS[0],status="done",source_ids=[src["id"]],title="mock"),range(15)))
    assert len(repo.videos("cong-nghe"))==len(repo.videos("cong-nghe",src["id"]))==1
    with repo.connection() as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0]=="wal"
    assert repo.videos("tin-tuc")==[]
    assert Repository(repo.path,user_id=2).sources("cong-nghe")==[]
    assert source(cfg)["id"]==src["id"]


def test_preview_stops_at_known_boundary_and_uses_uploads_no_search(cfg):
    src=source(cfg);repo=Repository.for_settings(cfg)
    repo.save_video("cong-nghe","youtube",IDS[1],status="done",title="known")
    api=Catalog([detail(i) for i in range(4)],pages=[[IDS[0],IDS[1]],[IDS[2],IDS[3]]])
    gemini=Mock()
    result=preview_scan(cfg,"công nghệ",api=api,now=NOW)
    assert [r["video_id"] for r in result["videos"] if r["decision"]=="ready"]==[IDS[0]]
    assert sum(endpoint=="playlistItems" for endpoint,_,_ in api.calls)==1
    assert not any(endpoint=="search" for endpoint,_,_ in api.calls)
    assert repo.source(src["id"])["last_scanned_at"]
    gemini.assert_not_called()


def test_preview_duration_age_private_and_batch_limit(cfg):
    source(cfg)
    api=Catalog([detail(0,seconds=300),detail(1,age=181),detail(2,privacyStatus="private"),detail(3),detail(4),detail(5),detail(6)])
    result=preview_scan(cfg,"cong-nghe",api=api,maximum=2,now=NOW)
    assert len([r for r in result["videos"] if r["decision"]=="ready"])==2
    assert len([r for r in result["videos"] if r["decision"]=="skipped"])==3
    repo=Repository.for_settings(cfg)
    assert repo.video("cong-nghe","youtube",IDS[0])["status"]=="skipped"
    assert repo.video("cong-nghe","youtube",IDS[6]) is None
    assert any("Quá cũ" in r["reason"] for r in result["videos"])


def test_keyword_uses_official_search_with_order_and_duration_filter(cfg):
    source(cfg,"keyword")
    result=preview_scan(cfg.model_copy(update={"scan_max_video_sec":600}),"cong-nghe",api=(api:=Catalog([detail(0),detail(1,seconds=240)])),mode="regular",order="viewCount",now=NOW)
    assert [r["video_id"] for r in result["videos"] if r["decision"]=="ready"]==[IDS[1]]
    assert api.calls[0][0]=="search" and api.calls[0][1]["order"]=="viewCount" and api.calls[0][2]["keyword"]


def test_scan_multiple_sources_global_limit_dedup_and_error_isolation(cfg):
    first=source(cfg)
    Repository.for_settings(cfg).add_source("cong-nghe","keyword","AI","AI")
    result=preview_scan(cfg,"cong-nghe",api=Catalog([detail(i) for i in range(6)]),maximum=2,now=NOW)
    ready_rows=[r for r in result["videos"] if r["decision"]=="ready"]
    assert len(ready_rows)==2 and all(len(r["source_ids"])==2 for r in ready_rows)
    api=Catalog([detail(0)])
    original=api.request
    api.request=lambda endpoint,params,**kw: (_ for _ in ()).throw(RuntimeError("fixture-scan-youtube-secret broken")) if endpoint=="channels" else original(endpoint,params,**kw)
    result=preview_scan(cfg,"cong-nghe",api=api,now=NOW)
    assert result["warnings"] and any(r["decision"]=="ready" for r in result["videos"])
    assert "fixture-scan-youtube-secret" not in json.dumps(result)


def test_approval_estimate_and_one_failure_can_retry_without_reanalyzing_done(cfg):
    provider=Mock();provider.analyze_url.side_effect=[RuntimeError("fixture-scan-gemini-secret failure"),observed()]
    rows=[ready(0),ready(1)]
    with pytest.raises(ValueError,match="xác nhận"):
        learn_selected(cfg,"cong-nghe",rows,provider=provider)
    provider.analyze_url.assert_not_called()
    assert estimate_selection(cfg,rows)["duration_sec"]==60
    result=learn_selected(cfg,"cong-nghe",rows,confirmed=True,provider=provider)
    assert [r["status"] for r in result["results"]]==["failed","done"]
    assert "fixture-scan-gemini-secret" not in json.dumps(result)
    failed=retry_candidates(cfg,"cong-nghe")
    assert [r["video_id"] for r in failed]==[IDS[0]]
    provider.analyze_url.side_effect=None;provider.analyze_url.return_value=observed()
    learn_selected(cfg,"cong-nghe",failed,confirmed=True,provider=provider)
    before=provider.analyze_url.call_count
    learn_selected(cfg,"cong-nghe",rows,confirmed=True,provider=provider)
    assert provider.analyze_url.call_count==before
    profile=rebuild_category(cfg,"cong-nghe")
    assert profile.video_count==2 and len(profile.reference_texts)>0
    assert all(r["status"]=="done" for r in Repository.for_settings(cfg).videos("cong-nghe"))


def test_new_url_results_merge_with_local_and_permanent_skip_excluded(cfg):
    from pipeline.style_learner import analyze_one
    path=cfg.root_dir/"assets/reference_videos/cong-nghe/local.mp4"
    path.parent.mkdir(parents=True);path.write_bytes(b"local video")
    provider=Mock();provider.analyze.return_value=observed();provider.analyze_url.return_value=observed()
    analyze_one(cfg,"cong-nghe/local.mp4",provider=provider)
    assert len(Repository.for_settings(cfg).videos("cong-nghe"))==1
    learn_selected(cfg,"cong-nghe",[ready(0)],provider=provider,confirmed=True)
    assert rebuild_category(cfg,"cong-nghe").video_count==2
    Repository.for_settings(cfg).skip_forever("cong-nghe","youtube",IDS[0])
    assert rebuild_category(cfg,"cong-nghe").video_count==1
    calls=provider.analyze_url.call_count
    learn_selected(cfg,"cong-nghe",[ready(0)],provider=provider,confirmed=True)
    assert provider.analyze_url.call_count==calls


def test_url_provider_sends_uri_without_files_or_downloads(cfg,monkeypatch):
    from pipeline.style_learner import VideoStyleProvider
    llm=Mock();llm.generate_media_json.return_value=observed().model_dump_json()
    monkeypatch.setattr("pipeline.style_learner.GeminiProvider",lambda settings:llm)
    provider=VideoStyleProvider(cfg)
    provider.analyze_url(ready()["url"],"same style prompt",lambda message:None)
    llm.client.files.upload.assert_not_called();llm.client.files.delete.assert_not_called()
    part=llm.generate_media_json.call_args.args[1]
    assert part.file_data.file_uri==ready()["url"] and part.file_data.mime_type=="video/mp4"


def test_relearn_reuses_existing_raw_and_keeps_old_success(cfg):
    provider=Mock();provider.analyze_url.return_value=observed()
    learn_selected(cfg,"cong-nghe",[ready()],provider=provider,confirmed=True)
    row=Repository.for_settings(cfg).video("cong-nghe","youtube",IDS[0])
    before=(cfg.root_dir/row["analysis_path"]).read_bytes()
    provider.analyze_url.side_effect=RuntimeError("temporary failure")
    result=learn_selected(cfg,"cong-nghe",retry_candidates(cfg,"cong-nghe",video_id=IDS[0],relearn=True),provider=provider,confirmed=True)
    assert result["results"][0]["status"]=="done"
    provider.analyze_url.assert_called_once()
    assert (cfg.root_dir/row["analysis_path"]).read_bytes()==before
    assert rebuild_category(cfg,"cong-nghe").video_count==1


def install_requests(monkeypatch,fail_once=False):
    calls=[]
    def get(url,**kwargs):
        assert url.startswith("https://www.googleapis.com/youtube/v3/")
        calls.append((url,kwargs))
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.json.return_value={"items":[]}
        if fail_once and len(calls)==1:
            failed=requests.Response();failed.status_code=503
            response.raise_for_status.side_effect=requests.HTTPError("retry mock",response=failed)
        return response
    monkeypatch.setattr("sources.youtube.requests.get",get)
    return calls


def test_quota_search_100_lists_1_cache_and_daily_cap(cfg,monkeypatch):
    calls=install_requests(monkeypatch)
    api=YouTubeCatalog(cfg.model_copy(update={"youtube_daily_quota":103}))
    api.request("channels",{"id":CHANNEL},cached=True)
    api.request("channels",{"id":CHANNEL},cached=True)
    api.request("videos",{"id":IDS[0]})
    api.request("search",{"q":"AI"},keyword=True)
    assert api.quota()["estimated_units"]==102 and len(calls)==3
    with pytest.raises(QuotaExceeded):
        api.request("search",{"q":"more"},keyword=True)
    assert len(calls)==3
    assert "fixture-scan-youtube-secret" not in (cfg.logs_dir/"researcher_errors.log").read_text(encoding="utf-8")


def test_quota_counts_each_retry_and_keyword_daily_limit(cfg,monkeypatch):
    calls=install_requests(monkeypatch,fail_once=True)
    api=YouTubeCatalog(cfg.model_copy(update={"retry_attempts":2,"youtube_max_searches_per_run":1}))
    api.request("videos",{"id":IDS[0]})
    assert len(calls)==2 and api.quota()["estimated_units"]==2
    api.request("search",{"q":"AI"},keyword=True)
    with pytest.raises(QuotaExceeded):
        YouTubeCatalog(api.settings).request("search",{"q":"another"},keyword=True)
    assert api.quota()["estimated_units"]==102


def test_cli_preview_requires_yes_and_channel_choice_not_automatic(cfg,monkeypatch,capsys):
    monkeypatch.setattr("pipeline.scan_sources.get_settings",lambda:cfg)
    monkeypatch.setattr("pipeline.scan_sources.YouTubeCatalog",lambda settings:Catalog([detail(0)]))
    source(cfg)
    learner=Mock();monkeypatch.setattr("pipeline.scan_sources.learn_selected",learner)
    monkeypatch.setattr("pipeline.scan_sources.sys.stdin",SimpleNamespace(isatty=lambda:False))
    assert main(["--category","công nghệ","--scan"])==0
    learner.assert_not_called()
    learner.return_value={"results":[],"warnings":[]}
    assert main(["--category","công nghệ","--scan","--yes"])==0
    assert learner.call_args.kwargs["confirmed"]
    monkeypatch.setattr("pipeline.scan_sources.resolve_source",lambda *a,**kw:{"choices":[{"kind":"channel","value":CHANNEL,"label":"Mock channel","source_url":""}],"requires_selection":True})
    assert main(["--category","công nghệ","--add","Tên kênh","--yes"])==2
    assert "--choose" in capsys.readouterr().out


def test_local_existing_analysis_import_and_cached_rebuild_does_not_call_gemini(cfg):
    from pipeline.style_library import record_path
    from tests.test_style_learner import record
    from pipeline.style_learner import digest_file
    from utils.cache import cache_key
    path=cfg.root_dir/"assets/reference_videos/cong-nghe/existing.mp4"
    path.parent.mkdir(parents=True);path.write_bytes(b"existing video")
    saved=record("cong-nghe/existing.mp4",digest_file(path));saved.notes_hash=cache_key("")
    target=record_path(cfg,"cong-nghe/existing.mp4")
    target.parent.mkdir(parents=True)
    target.write_text(saved.model_dump_json(),encoding="utf-8")
    profile=rebuild_category(cfg,"cong-nghe")
    assert profile.video_count==1
    assert Repository.for_settings(cfg).video("cong-nghe","local",digest_file(path))["status"]=="done"
    assert rebuild_category(cfg,"cong-nghe").source_signature==profile.source_signature


def test_source_toggle_and_skip_forever_never_sends_gemini(cfg):
    item=source(cfg);repo=Repository.for_settings(cfg)
    repo.activate(item["id"],False)
    api=Mock()
    with pytest.raises(ValueError,match="nguồn"):
        preview_scan(cfg,"cong-nghe",api=api)
    api.request.assert_not_called()
    repo.skip_forever("cong-nghe","youtube",IDS[0])
    provider=Mock()
    result=learn_selected(cfg,"cong-nghe",[ready()],confirmed=True,provider=provider)
    assert result["results"][0]["status"]=="cached"
    provider.analyze_url.assert_not_called()


def test_gemini_attempt_observer_counts_retries(cfg,monkeypatch):
    from google.genai import errors
    from pipeline.style_learner import VideoStyleProvider
    from providers.llm_gemini import GeminiProvider
    client=Mock();client.models.generate_content.side_effect=[
        errors.ServerError(503,{"error":{"message":"mock unavailable"}}),
        SimpleNamespace(candidates=[],prompt_feedback=None,text=observed().model_dump_json())]
    monkeypatch.setattr("providers.llm_gemini.genai.Client",lambda **kwargs:client)
    provider=VideoStyleProvider(cfg.model_copy(update={"retry_attempts":2}))
    result=provider.analyze_url(ready()["url"],"style analysis prompt",lambda message:None)
    assert result.scenes and Repository.for_settings(cfg).daily_calls("gemini_style")==2
    client.files.upload.assert_not_called()
    provider.close()


def test_search_retry_costs_100_each(cfg,monkeypatch):
    calls=install_requests(monkeypatch,fail_once=True)
    api=YouTubeCatalog(cfg.model_copy(update={"retry_attempts":2}))
    api.request("search",{"q":"mock"},keyword=True)
    assert len(calls)==2 and api.quota()["estimated_units"]==200
    assert api.quota()["search_calls"]==2


def test_scan_ui_channel_selection_and_preview_consent(cfg,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from app.views import style_sources
    monkeypatch.setattr("config.settings.get_settings",lambda:cfg)
    manager=Mock();manager.active.return_value=None;manager.snapshot.return_value=None
    manager.submit_learning.return_value="learn-mock"
    monkeypatch.setattr(style_sources,"scan_jobs",lambda:manager)
    resolver=Mock(return_value={"choices":[{"kind":"channel","value":CHANNEL,"label":"Chosen channel","source_url":"https://www.youtube.com/channel/"+CHANNEL,"thumbnail_url":""}],"requires_selection":True})
    monkeypatch.setattr(style_sources,"resolve_source",resolver)
    at=AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=30).run()
    at.sidebar.radio[0].set_value("Phong cách mẫu").run()
    at.session_state["style_category_tabs"]="công nghệ";at.run()
    assert not at.exception
    at.text_input(key="scan_value_cong-nghe").set_value("Tên kênh mock")
    next(b for b in at.button if b.label=="Thêm nguồn").click().run()
    assert not at.exception and not Repository.for_settings(cfg).sources("cong-nghe")
    select=next(v for v in at.selectbox if v.label.startswith("Chọn đúng kênh"))
    select.set_value(CHANNEL).run()
    next(b for b in at.button if b.label=="Xác nhận kênh đã chọn").click().run()
    assert not at.exception and Repository.for_settings(cfg).sources("cong-nghe")
    at.session_state["style_scan_preview_cong-nghe"]={"videos":[ready()],"warnings":[],"created_at":"mock"}
    at.run()
    assert next(b for b in at.button if b.label=="Xác nhận học video đã chọn").disabled
    manager.submit_learning.assert_not_called()
    next(c for c in at.checkbox if c.label.startswith("Tôi xác nhận gọi Gemini")).check().run()
    next(b for b in at.button if b.label=="Xác nhận học video đã chọn").click().run()
    assert not at.exception
    assert manager.submit_learning.call_args.args[2][0]["video_id"]==IDS[0]


def test_preview_can_permanently_skip_before_any_paid_analysis(cfg,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from app.views import style_sources
    monkeypatch.setattr("config.settings.get_settings",lambda:cfg)
    manager=Mock();manager.active.return_value=None;manager.snapshot.return_value=None
    monkeypatch.setattr(style_sources,"scan_jobs",lambda:manager)
    at=AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=30).run()
    at.sidebar.radio[0].set_value("Phong cách mẫu").run()
    at.session_state["style_category_tabs"]="công nghệ"
    at.session_state["style_scan_preview_cong-nghe"]={"videos":[ready()],"warnings":[],"created_at":"mock"}
    at.run()
    at.button(key="scan_preview_skip_cong-nghe"+IDS[0]).click().run()
    assert not at.exception
    row=Repository.for_settings(cfg).video("cong-nghe","youtube",IDS[0])
    assert row["permanent_skip"] and row["title"]==ready()["title"]
    manager.submit_learning.assert_not_called()


def test_returning_to_category_does_not_reapply_an_old_worker_result(cfg,monkeypatch):
    from app.views import style_sources
    manager=Mock();manager.snapshot.return_value={"status":"finished","message":"Old scan","error":None,"kind":"scan","result":{"videos":[],"created_at":"old"}}
    monkeypatch.setattr(style_sources,"scan_jobs",lambda:manager)
    state={"style_scan_worker_cong-nghe":"job-a","style_scan_applied_cong-nghe":"job-a",
        "style_scan_applied":"job-b","style_scan_preview_cong-nghe":{"videos":[],"created_at":"user-selection"}}
    monkeypatch.setattr(style_sources.st,"session_state",state)
    monkeypatch.setattr(style_sources.st,"fragment",lambda **kwargs:lambda fn:fn)
    monkeypatch.setattr(style_sources.st,"info",Mock())
    rerun=Mock();monkeypatch.setattr(style_sources.st,"rerun",rerun)
    style_sources.show_worker(cfg,"cong-nghe",Mock())
    assert state["style_scan_preview_cong-nghe"]["created_at"]=="user-selection"
    rerun.assert_not_called()


def test_corrupt_quota_is_a_clear_value_error_not_ui_keyerror(cfg):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    cfg.cache_dir.mkdir()
    path=cfg.cache_dir/"youtube_quota.json"
    path.write_text(json.dumps({"day":datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()}),encoding="utf-8")
    with pytest.raises(ValueError,match="quota local"):
        YouTubeCatalog(cfg).quota()
