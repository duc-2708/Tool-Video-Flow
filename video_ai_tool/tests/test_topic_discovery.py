"""Offline RSS, grouping, model provenance, history and pipeline handoff."""
import json
from datetime import datetime,timedelta,timezone
from email.utils import format_datetime
from unittest.mock import Mock
import pytest
from config.settings import Settings,ROOT_DIR
from config.categories import load_categories,save_categories
from schemas.topic_discovery import CategoryFile,TopicSuggestion,DiscoveryHint
from sources.topic_discovery import parse_feed,cluster_news,discover_topics,validate_suggestion,rank_score
from pipeline.topics_history import already_made,record_topic,history_rows
from pipeline.discover import topic_config,launch_topic,auto_pick
from utils.cache import write_json
from tests.test_run_all import stages

NOW=datetime(2026,10,21,12,tzinfo=timezone.utc)
TITLE="Gemini 4 ra mắt tính năng mới"


def config():
    return CategoryFile.model_validate({"categories":[{"name":"công nghệ","keywords_vi":["công nghệ"],"keywords_en":["technology"],
        "suggested_type":"news","rss":[{"name":"Alpha","url":"https://alpha.test/rss","region":"vn"},
        {"name":"Beta","url":"https://beta.test/rss","region":"global"}]}]})


def rss(entries):
    return "<rss version='2.0'><channel><title>Feed</title>"+"".join(
        f"<item><title>{title}</title><link>{url}</link><pubDate>{format_datetime(when)}</pubDate></item>" for title,url,when in entries)+"</channel></rss>"


def articles():
    return [{"title":TITLE,"url":"https://alpha.test/gemini-4","source":"Alpha","region":"vn","published_at":NOW.isoformat()},
        {"title":TITLE+" hôm nay","url":"https://beta.test/gemini-4","source":"Beta","region":"global","published_at":NOW.isoformat()}]


def suggestion(group=None):
    group=group or cluster_news(articles())[0]
    return {"cluster_id":group["id"],"topic":TITLE,"why_now":"Hai nguồn đang đưa tin.","angle":"Giải thích tính năng đã kiểm chứng.",
        "suggested_type":"news","search_queries":{"vi":["Gemini 4 tính năng mới"],"en":["Gemini 4 new features"]},
        "score":8,"score_reason":"Mới và có hai nguồn độc lập.","source_urls":[a["url"] for a in group["articles"]]}


class FakeGemini:
    model_name="fake-discovery"
    def __init__(self,broken=False): self.broken=broken;self.calls=[]
    def generate_json(self,prompt,schema):
        self.calls.append(prompt)
        if self.broken: raise RuntimeError("Gemini fixture unavailable")
        data=json.loads(prompt.split("INPUT_DATA_JSON:\n")[-1])
        return json.dumps({"topics":[suggestion(g) for g in data["groups"]]},ensure_ascii=False)
    def close(self): pass


def test_feed_filters_old_future_and_missing_date():
    feed=config().categories[0].rss[0]
    rows,notices=parse_feed(rss([(TITLE,"https://alpha.test/new",NOW),
        ("Old story","https://alpha.test/old",NOW-timedelta(days=4)),
        ("Future story","https://alpha.test/future",NOW+timedelta(days=1))]),feed,NOW,3)
    assert len(rows)==1 and rows[0]["title"]==TITLE
    assert any("loại 2" in notice for notice in notices)


def test_groups_deduplicate_urls_but_keep_independent_publishers():
    rows=articles()
    rows.append(dict(rows[0]))
    groups=cluster_news(rows)
    assert len(groups)==1 and len(groups[0]["articles"])==2 and groups[0]["source_count"]==2


@pytest.mark.parametrize("change",["url","number","name","roundup"])
def test_model_cannot_invent_urls_or_event_names(change):
    group=cluster_news(articles())[0];data=suggestion(group)
    if change=="url": data["source_urls"]=["https://invented.test/fake"]
    if change=="number": data["topic"]="Gemini 999 ra mắt tính năng mới"
    if change=="name": data["topic"]="Gemini 4 và FakeCorp ra mắt tính năng mới"
    if change=="roundup": data["topic"]="Tổng hợp Gemini 4 và nhiều tin mới"
    with pytest.raises(ValueError): validate_suggestion(TopicSuggestion.model_validate(data),group)


def test_discovery_falls_back_to_raw_news_when_gemini_or_feed_fails(tmp_path):
    settings=Settings(root_dir=tmp_path,retry_attempts=1)
    def load(feed,settings):
        if feed.region=="global": raise RuntimeError("RSS fixture blocked")
        return rss([(TITLE,"https://alpha.test/new",NOW)])
    result=discover_topics("công nghệ",settings,categories=config(),now=NOW,count=5,feed_loader=load,
        searcher=lambda *args:[],provider=FakeGemini(broken=True))
    assert result["gemini_error"] and result["topics"] and result["raw_news"]
    assert any(s["status"]=="failed" for s in result["sources"])
    assert "blocked" in " ".join(result["warnings"])


def test_old_history_topics_are_filtered_before_auto_pick(tmp_path):
    settings=Settings(root_dir=tmp_path)
    write_json(settings.output_dir/"topics_history.json",{"topics":[{"topic":TITLE,"category":"công nghệ","date":NOW.isoformat(),"project":"done"}]})
    result=discover_topics("công nghệ",settings,categories=config(),now=NOW,count=5,
        feed_loader=lambda feed,settings:rss([(TITLE,f"https://{feed.name.lower()}.test/gemini-4",NOW)]),
        searcher=lambda *args:[],provider=FakeGemini())
    assert not result["topics"] and result["excluded_history"]
    assert not already_made(TITLE,[{"topic":TITLE,"date":(NOW-timedelta(days=15)).isoformat(),"project":"old"}],NOW)


def test_auto_pick_rechecks_history_and_launch_maps_review(monkeypatch,tmp_path):
    settings=Settings(root_dir=tmp_path)
    first=suggestion();second={**first,"topic":"Apple ra mắt iPhone 18","cluster_id":"other","source_urls":["https://apple.test/iphone18"]}
    record_topic(settings.output_dir,TITLE,"công nghệ",tmp_path/"old")
    assert auto_pick({"topics":[first,second]},settings)==second
    run=Mock(return_value=tmp_path/"new")
    monkeypatch.setattr("pipeline.discover.run_all",run)
    launch_topic(second,"công nghệ",settings)
    cfg=run.call_args.args[0]
    assert cfg.topic==second["topic"] and cfg.video_type=="news" and cfg.mode=="review" and cfg.ai_clips==0
    assert cfg.discovery.suggestion.search_queries.en==first["search_queries"]["en"]


def test_pipeline_passes_discovery_queries_and_credits_without_replacing_research(stages,monkeypatch):
    import pipeline.run_all as module
    settings,calls,_,_=stages
    hint=DiscoveryHint(category="công nghệ",suggestion=TopicSuggestion.model_validate(suggestion()))
    original=module.run_research;seen={}
    def research(*args,**kwargs):
        seen.update(kwargs);return original(*args,**kwargs)
    monkeypatch.setattr(module,"run_research",research)
    project=module.run_all(topic_config(hint.suggestion,hint.category),settings=settings)
    assert calls==["research","director"] and seen["discovery_hint"]==hint
    assert (project/"topic_discovery.json").is_file()
    assert not history_rows(settings.output_dir)  # Review is not a completed video.
    module.run_all(module.saved_config(project,continue_after_review=True),settings=settings)
    assert any(r["project"]==str(project) for r in history_rows(settings.output_dir))
    report=(project/"report.md").read_text(encoding="utf-8")
    assert "https://alpha.test/gemini-4" in report and "NGUỒN KHÁM PHÁ" in report


def test_category_configuration_round_trip(tmp_path):
    path=tmp_path/"categories.yaml"
    data=config().model_dump(mode="json");data["categories"][0]["rss"][0]["enabled"]=False
    save_categories(data,path)
    assert not load_categories(path).categories[0].rss[0].enabled
    defaults=load_categories()
    assert len(defaults.categories)==9 and all({f.region for f in c.rss}=={"vn","global"} for c in defaults.categories)


def test_optional_youtube_failure_keeps_discovery(tmp_path,monkeypatch):
    monkeypatch.setattr("sources.youtube_trends.YouTubeTrends.collect",Mock(side_effect=RuntimeError("quota")))
    settings=Settings(root_dir=tmp_path)
    result=discover_topics("công nghệ",settings,categories=config(),now=NOW,count=1,use_youtube=True,
        feed_loader=lambda f,s:rss([(TITLE,"https://alpha.test/new",NOW)]),searcher=lambda *args:[],provider=FakeGemini())
    assert result["topics"] and any("quota" in w for w in result["warnings"])


def test_first_ui_page_and_manual_handoff(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr("config.settings.get_settings",lambda:Settings(root_dir=tmp_path))
    app=AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=25).run()
    assert not app.exception and app.sidebar.radio[0].value=="Tạo video theo danh mục"
    app.sidebar.radio[0].set_value("Khám phá chủ đề").run()
    app.text_input(key="discovery_manual").set_value("Sự kiện cụ thể của tôi").run()
    next(b for b in app.button if b.label=="Dùng chủ đề tự nhập").click().run()
    assert not app.exception and app.sidebar.radio[0].value=="Tạo video"
    assert app.text_input(key="create_topic").value=="Sự kiện cụ thể của tôi"


def test_new_event_action_not_present_in_titles_is_rejected():
    data=suggestion();data["topic"]="Gemini 4 phá sản"
    with pytest.raises(ValueError,match="loại sự kiện"):
        validate_suggestion(TopicSuggestion.model_validate(data),cluster_news(articles())[0])


def test_same_source_history_blocks_cross_language_retitle():
    rows=[{"topic":"Gemini ra mắt","date":NOW.isoformat(),"project":"created","source_urls":["https://alpha.test/event"]}]
    assert already_made("A totally translated title",rows,NOW,source_urls=["https://alpha.test/event"])


def test_director_angle_is_unverified_metadata(tmp_path):
    from tests.test_director import fixture_brief,fixture_plan,FakeDirector
    from agents.director import DirectorRequest,create_edit_plan,director_diagnostics
    from utils.cache import JsonCache
    brief=fixture_brief()
    brief.discovery_hint=DiscoveryHint(category="công nghệ",suggestion=TopicSuggestion.model_validate(suggestion()))
    settings=Settings(root_dir=tmp_path)
    settings.prompts_dir.mkdir()
    for path in (ROOT_DIR/"prompts").glob("director*.txt"):
        (settings.prompts_dir/path.name).write_text(path.read_text(encoding="utf-8"),encoding="utf-8")
    provider=FakeDirector([fixture_plan()])
    create_edit_plan(brief,DirectorRequest(video_type="news",video_format="tiktok",duration_sec=45,script_style=None),
        provider,settings,JsonCache(settings.cache_dir),director_diagnostics(settings),lambda _:None)
    data=json.loads(provider.prompts[0][1].split("INPUT_DATA_JSON:\n")[-1])
    assert data["discovery_hint"]["suggestion"]["angle"]==suggestion()["angle"]
    assert all(row["fact_vi"]!=suggestion()["angle"] for row in data["facts"])


def test_research_uses_hint_queries_but_still_collects_and_grounds(tmp_path,monkeypatch):
    from pydantic import SecretStr
    import agents.researcher as researcher
    from schemas.source import SourceDocument
    from schemas.research_brief import SearchQuery
    from tests.test_director import fixture_brief
    settings=Settings(root_dir=tmp_path,gemini_model="mock",gemini_api_key=SecretStr("fake-private"))
    source=SourceDocument(title="Verified article",url="https://alpha.test/article",source_name="Alpha",platform="web",text="Content "*60,
        retrieved_at=NOW.isoformat(),content_kind="article",source_lang="en")
    provider=Mock(model_name="mock")
    monkeypatch.setattr(researcher,"GeminiProvider",lambda *args:provider)
    monkeypatch.setattr(researcher,"generate_queries",lambda *args:[SearchQuery(source_lang="en",region="us-en",query="independent verification query")])
    collector=Mock()
    collector.collect.return_value=([source],[])
    collector.summarize.return_value={"found":1,"kept":1,"discarded":0}
    monkeypatch.setattr(researcher,"WebSearch",lambda *args:collector)
    grounded=Mock(return_value=fixture_brief())
    monkeypatch.setattr(researcher,"create_brief",grounded)
    hint=DiscoveryHint(category="công nghệ",suggestion=TopicSuggestion.model_validate(suggestion()))
    path=researcher.run_research(TITLE,settings,source_languages=["en"],use_youtube=False,discovery_hint=hint,progress=lambda _:None)
    queries=[call.args[0] for call in collector.collect.call_args_list]
    assert hint.suggestion.search_queries.en[0] in queries and "independent verification query" in queries
    grounded.assert_called_once()
    assert json.loads(path.read_text(encoding="utf-8"))["discovery_hint"]["suggestion"]["angle"]==hint.suggestion.angle


def test_rss_roundup_is_not_auto_selected_as_one_event():
    feed=config().categories[0].rss[0]
    rows,_=parse_feed(rss([("Tổng hợp tin công nghệ hôm nay","https://alpha.test/roundup",NOW),
        (TITLE,"https://alpha.test/event",NOW)]),feed,NOW,3)
    assert [r["title"] for r in rows]==[TITLE]


def test_raw_news_handoff_preserves_source_metadata(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr("config.settings.get_settings",lambda:Settings(root_dir=tmp_path))
    app=AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=25).run()
    app.sidebar.radio[0].set_value("Khám phá chủ đề").run()
    app.session_state["discovery_result"]={"category":"công nghệ","topics":[],"sources":[],"warnings":[],
        "gemini_error":"fixture unavailable","excluded_history":[],"raw_news":articles(),"groups":cluster_news(articles()),"generated_at":NOW.isoformat()}
    app.run()
    next(b for b in app.button if b.label=="Dùng tiêu đề tin thô").click().run()
    assert not app.exception and app.sidebar.radio[0].value=="Tạo video"
    data=app.session_state["create_discovery"]
    assert "https://alpha.test/gemini-4" in data["suggestion"]["source_urls"]
