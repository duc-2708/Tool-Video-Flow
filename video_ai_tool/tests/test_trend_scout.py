"""Offline Trend Scout regression: real redacted probes + controlled fake APIs."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from unittest.mock import Mock
import pytest
import requests
from pydantic import SecretStr

from config.categories import resolve_category
from config.settings import ROOT_DIR, Settings
from config.trends import TrendConfig, load_trends
from db.repository import Repository
from pipeline.trend_scout import scout, group_items, score_topics, as_suggestion
from providers.trends.scrapecreators_tiktok import ScrapeCreatorsTikTok, adapt
from schemas.trends import TrendItem, TrendTopic
from utils.diagnostics import Diagnostics
from tests.test_run_all import stages

FIXTURES = ROOT_DIR / "tests/fixtures"


@pytest.fixture
def settings(tmp_path):
    return Settings(root_dir=tmp_path, scrapecreators_api_key=SecretStr("private-scout-fixture"))


def config(**updates):
    return TrendConfig(enabled=True, gemini_enabled=False, providers={"scrapecreators_tiktok": True},
        categories={"cong-nghe": {"keywords": ["AI"], "subreddits": ["technology"]}}, **updates)


def item(title="Công nghệ thử nghiệm ra mắt", identity="one", platform="tiktok", score=100):
    return TrendItem(id=identity, title=title, url=f"https://example.com/{identity}",
                     platform=platform, language="vi", score_raw=score)


def topic(source, title=None):
    return TrendTopic(topic_title_vi=title or source.title, why_hot="Đang được quan tâm.",
        angle_suggestions=["Cơ chế hoạt động", "Ý nghĩa với người dùng"], score_hot=8,
        score_fit_category=8, score_vietnam_audience=8, sources=[source.url])


@pytest.mark.parametrize("name,container", [("trending_vn", "aweme_list"), ("trending_us", "aweme_list"),
    ("keyword_ai", "search_item_list"), ("hashtag_ai", "aweme_list")])
def test_adapter_real_redacted_probe(name, container):
    record = json.loads((FIXTURES / f"scrapecreators_{name}.json").read_text(encoding="utf-8"))
    assert record["provenance"] == "live_probe" and record["http_status"] == 200
    raw = record["payload"]
    assert raw["credits_charged"] == 1 and raw[container]
    rows = adapt(raw)
    assert rows and all(r.platform == "tiktok" and r.metrics.views >= 0 for r in rows)
    projection = json.dumps(raw, ensure_ascii=False)
    assert '"author"' not in projection and '"avatar"' not in projection and "play_addr" not in projection
    assert all("/@redacted/" in str(r.url) for r in rows)


@pytest.mark.parametrize("payload", [None, [], {}, {"aweme_list": None}, {"aweme_list": [None, {}, {"aweme_info": None}]},
    {"search_item_list": [{"aweme_info": {"aweme_id": "1", "desc": None, "statistics": None}}]}])
def test_adapter_missing_null(payload):
    assert adapt(payload) == []


def test_adapter_metrics_null_and_no_media_links():
    payload = {"aweme_list": [{"aweme_id": "42", "desc": "AI #technology", "statistics": None,
        "url": "https://www.tiktok.com/@person/video/42", "video": {"play_addr": "https://private-cdn/video.mp4"}}]}
    row = adapt(payload)[0]
    assert row.metrics.views == 0 and row.language == "und" and row.hashtags == ["technology"]
    assert "private-cdn" not in row.model_dump_json()


def test_cache_hit_no_credit_and_budget_counts_actual_attempts(settings, monkeypatch):
    raw = json.loads((FIXTURES / "scrapecreators_keyword_ai.json").read_text(encoding="utf-8"))["payload"]
    source = ScrapeCreatorsTikTok(settings, config(TREND_DAILY_CREDIT_LIMIT=1))
    send = Mock(return_value=raw)
    monkeypatch.setattr(source, "request", send)
    first = source._call("/v1/tiktok/search/keyword", {"query": "AI"})
    assert first and source._call("/v1/tiktok/search/keyword", {"query": "AI"}) == first
    assert source._call("/v1/tiktok/search/keyword", {"query": "different"}) == []
    send.assert_called_once()
    assert "private-scout-fixture" not in (settings.logs_dir / "trend_scout_errors.log").read_text(encoding="utf-8")
    assert Repository.for_settings(settings).trend_usage()["requests"] == 1
    assert Repository.for_settings(settings).trend_usage()["reported_credits"] == 1


@pytest.mark.parametrize("error", [requests.Timeout("timeout"), RuntimeError("HTTP 401"), RuntimeError("HTTP 429")])
def test_failed_paid_request_counted_not_retried(settings, monkeypatch, error):
    source = ScrapeCreatorsTikTok(settings, config())
    send = Mock(side_effect=error)
    monkeypatch.setattr(source, "request", send)
    assert not source._call("/v1/tiktok/search/keyword", {"query": "AI"})
    send.assert_called_once()
    assert Repository.for_settings(settings).trend_usage()["requests"] == 1
    assert Repository.for_settings(settings).trend_usage()["reported_calls"] == 0


def test_no_key_never_reserves_or_calls(settings, monkeypatch):
    source = ScrapeCreatorsTikTok(settings.model_copy(update={"scrapecreators_api_key": SecretStr("")}), config())
    send = Mock()
    monkeypatch.setattr(source, "request", send)
    assert source.fetch(resolve_category(settings, "công nghệ"), 5) == []
    send.assert_not_called()
    assert not (settings.root_dir / "data/app.db").exists()


def test_concurrent_credit_reservations_never_exceed_budget(settings):
    repo = Repository.for_settings(settings)
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(lambda _: repo.reserve_trend_call("scrapecreators", 3, "keyword"), range(20)))
    assert len([r for r in rows if r is not None]) == 3
    assert repo.trend_usage()["requests"] == 3


def test_credit_rollover_and_reported_charge(settings):
    repo = Repository.for_settings(settings)
    token = repo.reserve_trend_call("scrapecreators", 1, "feed", day="2001-01-01")
    repo.finish_trend_call(token, 1)
    assert repo.trend_usage()["requests"] == 0
    current = repo.reserve_trend_call("scrapecreators", 2, "feed")
    repo.finish_trend_call(current, 2)
    assert repo.reserve_trend_call("scrapecreators", 2, "feed") is None


class Working:
    warnings = []
    def __init__(self, *args, **kwargs): pass
    def fetch(self, category, limit): return [item()]


class Broken(Working):
    def fetch(self, *args): raise requests.Timeout("HTTP 429 private-scout-fixture")


def test_provider_error_does_not_lose_other_sources(settings):
    cfg = config().model_copy(update={"providers": {"broken": True, "working": True}})
    result = scout("công nghệ", settings, config=cfg, providers={"broken": Broken, "working": Working})
    assert len(result["topics"]) == 1 and result["warnings"]
    log = (settings.logs_dir / "trend_scout_errors.log").read_text(encoding="utf-8")
    assert "private-scout-fixture" not in log and "HTTP 429" in log


def test_disabled_does_not_call_any_provider_or_gemini(settings):
    llm = Mock()
    factory = Mock()
    cfg = config().model_copy(update={"enabled": False, "gemini_enabled": True})
    result = scout("công nghệ", settings, config=cfg, providers={"scrapecreators_tiktok": factory}, llm=llm)
    assert not result["topics"]
    factory.assert_not_called()
    llm.generate_json.assert_not_called()
    assert not (settings.root_dir / "data/app.db").exists()


def test_groups_merge_title_duplicates_but_not_distinct_events():
    a = item()
    b = item(title=a.title+" hôm nay", identity="two", platform="reddit")
    c = item("Ngân hàng giảm lãi suất", "three")
    assert len(group_items([a, a, b, c])) == 2
    assert sorted(map(len, group_items([a, a, b, c]))) == [1, 2]


def test_free_providers_take_only_metadata(settings, monkeypatch):
    from providers.trends.reddit import Reddit
    from providers.trends.hackernews import HackerNews
    from providers.trends.google_trends import GoogleTrends
    category = resolve_category(settings, "công nghệ")
    reddit = Reddit(settings, config())
    monkeypatch.setattr(reddit, "request", Mock(return_value={"data": {"children": [{"data": {
        "id": "r1", "title": "AI research progress", "score": 20, "num_comments": 3,
        "permalink": "/r/technology/comments/r1/ai/", "selftext": "DO NOT STORE FULL CONTENT",
        "media": {"reddit_video": {"fallback_url": "https://cdn.invalid/movie.mp4"}}}}]}}))
    rows = reddit.fetch(category, 5)
    assert rows and "DO NOT STORE" not in rows[0].model_dump_json() and "movie.mp4" not in rows[0].model_dump_json()
    hn = HackerNews(settings, config())
    monkeypatch.setattr(hn, "request", Mock(side_effect=[[1], {"title": "AI research progress", "score": 10,
        "descendants": 2, "text": "DO NOT STORE ARTICLE", "url": "https://article.test"}]))
    rows = hn.fetch(category, 5)
    assert rows and str(rows[0].url) == "https://news.ycombinator.com/item?id=1" and not rows[0].summary
    google = GoogleTrends(settings, config())
    monkeypatch.setattr(google, "request", Mock(return_value='<rss xmlns:ht="https://trends.google.com/trending/rss"><channel><item><title>AI launch</title><ht:approx_traffic>2,000+</ht:approx_traffic></item></channel></rss>'))
    rows = google.fetch(category, 5)
    assert rows and rows[0].metrics.views == 2000


@pytest.mark.parametrize("provider_name", ["reddit", "hackernews", "google_trends"])
def test_free_providers_timeout_is_warning(settings, monkeypatch, provider_name):
    from pipeline.trend_scout import provider_types
    provider = provider_types()[provider_name](settings, config())
    monkeypatch.setattr(provider, "request", Mock(side_effect=requests.Timeout("fixture timeout")))
    assert provider.fetch(resolve_category(settings, "công nghệ"), 5) == []
    assert provider.warnings and (settings.logs_dir / "trend_scout_errors.log").exists()


def test_region_is_part_of_paid_cache_key(settings, monkeypatch):
    repo = Repository.for_settings(settings)
    raw = json.loads((FIXTURES / "scrapecreators_trending_vn.json").read_text(encoding="utf-8"))["payload"]
    send = Mock(return_value=raw)
    for region in ("VN", "US", "VN"):
        source = ScrapeCreatorsTikTok(settings, config(), region=region, repository=repo)
        monkeypatch.setattr(source, "request", send)
        assert source._call("/v1/tiktok/get-trending-feed", {})
    assert send.call_count == 2 and repo.trend_usage()["requests"] == 2


def test_gemini_duplicate_topics_removed_and_invented_name_rejected(settings):
    source = item("Thiết bị thử nghiệm vừa ra mắt")
    class Source(Working):
        def fetch(self, *args): return [source]
    llm = Mock()
    good = topic(source).model_dump(mode="json")
    bad = {**good, "topic_title_vi": "FakeCorp ra mắt thiết bị mới"}
    llm.generate_json.return_value = json.dumps({"topics": [good, good, bad]})
    cfg = config().model_copy(update={"providers": {"working": True}, "gemini_enabled": True})
    result = scout("công nghệ", settings, config=cfg, providers={"working": Source}, llm=llm)
    assert len(result["topics"]) == 1 and "FakeCorp" not in result["topics"][0]["topic"]


def test_used_topics_fourteen_days_and_idempotent(settings):
    repo = Repository.for_settings(settings)
    repo.mark_topic_used(item().title, "cong-nghe", settings.output_dir / "p")
    repo.mark_topic_used(item().title, "cong-nghe", settings.output_dir / "p")
    assert len(repo.recent_topics()) == 1
    result = scout("công nghệ", settings, config=config().model_copy(update={"providers": {"working": True}}), providers={"working": Working})
    assert not result["topics"] and len(result["excluded_history"]) == 1
    assert not repo.recent_topics(now=datetime.now(timezone.utc)+timedelta(days=15))


def test_gemini_single_batch_rejects_invented_url_and_groups_again(settings):
    a = item()
    bad = {**topic(a).model_dump(mode="json"), "sources": ["https://invented.example/no"]}
    llm = Mock()
    llm.generate_json.return_value = json.dumps({"topics": [bad, topic(a).model_dump(mode="json")]})
    cfg = config().model_copy(update={"providers": {"working": True}, "gemini_enabled": True})
    result = scout("công nghệ", settings, config=cfg, providers={"working": Working}, llm=llm)
    assert len(result["topics"]) == 1
    llm.generate_json.assert_called_once()
    assert callable(llm.request_observer)
    assert "facts/evidence_quote" in llm.generate_json.call_args.args[0]


def test_gemini_failure_fallback_score_normalized(settings):
    llm = Mock()
    llm.generate_json.side_effect = RuntimeError("504 private-scout-fixture")
    result = scout("công nghệ", settings, config=config().model_copy(update={"providers": {"working": True}, "gemini_enabled": True}),
                   providers={"working": Working}, llm=llm)
    assert result["topics"] and result["gemini_error"] and result["trend_topics"][0]["score_hot"] == 10
    assert "private-scout-fixture" not in result["gemini_error"]


def test_gemini_prompt_bounded(settings):
    groups = [[item("Chủ đề thử nghiệm " + str(i) + "x"*190, str(i))] for i in range(150)]
    llm = Mock()
    llm.generate_json.return_value = '{"topics":[]}'
    score_topics(groups, resolve_category(settings, "công nghệ"), settings, Diagnostics(settings.logs_dir), lambda s: None, llm)
    assert len(llm.generate_json.call_args.args[0]) < 18000


def test_api_fetch_does_not_follow_redirect_or_download_media(settings, monkeypatch):
    from providers.trends.base import BaseProvider
    response = Mock(status_code=200)
    response.iter_content.return_value = [b'{"success":true}']
    context = Mock()
    context.__enter__ = Mock(return_value=response)
    context.__exit__ = Mock(return_value=False)
    get = Mock(return_value=context)
    monkeypatch.setattr("providers.trends.base.requests.get", get)
    assert BaseProvider(settings, config()).request("https://fixed.example/api") == {"success": True}
    assert get.call_args.kwargs["allow_redirects"] is False and get.call_args.kwargs["stream"] is True


def test_youtube_uses_one_list_quota_and_shared_ledger(settings, monkeypatch):
    from providers.trends.youtube_trending import YouTubeTrending
    settings = settings.model_copy(update={"youtube_api_key": SecretStr("fixture-youtube"), "retry_attempts": 1})
    response = Mock()
    response.json.return_value = {"items": [{"id": "abcdefghijk", "snippet": {"title": "AI technology"}, "statistics": {"viewCount": "50"}}]}
    context = Mock()
    context.__enter__ = Mock(return_value=response)
    context.__exit__ = Mock(return_value=False)
    send = Mock(return_value=context)
    monkeypatch.setattr("sources.youtube.requests.get", send)
    provider = YouTubeTrending(settings, config())
    category = resolve_category(settings, "công nghệ")
    assert provider.fetch(category, 5)
    assert provider.fetch(category, 5)
    send.assert_called_once()
    assert send.call_args.kwargs["params"]["chart"] == "mostPopular"
    ledger = json.loads((settings.cache_dir / "youtube_quota.json").read_text(encoding="utf-8"))
    assert ledger["estimated_units"] == 1 and ledger["search_calls"] == 0


def test_probe_privacy_projection_and_safe_error(settings):
    from tools.probe_scrapecreators import project_response
    raw = {"success": True, "aweme_list": [{"aweme_id": "42", "desc": "AI @secret https://personal.test",
        "author": {"unique_id": "secret-person", "avatar": "secret-image"},
        "url": "https://www.tiktok.com/@secret/video/42", "video": {"play_addr": "media"}}]}
    value = json.dumps(project_response(raw, Diagnostics(settings.logs_dir)))
    assert "@secret" not in value and "personal.test" not in value and "secret-person" not in value and "play_addr" not in value


def test_probe_without_key_does_not_make_api_call(tmp_path, monkeypatch):
    from tools.probe_scrapecreators import probe
    (tmp_path / ".env").write_text("", encoding="utf-8")
    get = Mock()
    monkeypatch.setattr("tools.probe_scrapecreators.requests.get", get)
    result = probe(tmp_path)
    assert result["status"] == "no_key" and not result["requests"]
    get.assert_not_called()


def test_research_facts_only_web_despite_tiktok_inspiration(settings):
    from agents.researcher import create_brief
    from schemas.topic_discovery import DiscoveryHint
    from schemas.source import SourceDocument
    from tests.test_researcher import FakeLLM, response_data
    from utils.cache import JsonCache
    source = SourceDocument(title="Fixture", url="https://example.com/article", source_name="example.com", platform="web",
        content_kind="article", text="Dữ liệu này chỉ là ví dụ phục vụ kiểm thử phần mềm.", retrieved_at="2026-10-20T00:00:00Z")
    data = response_data(source)
    bad = dict(data["facts"][0], source_url="https://www.tiktok.com/@sample/video/42", evidence_quote="Tín hiệu này không phải nguồn thật")
    data["facts"].append(bad)
    t = topic(item("Dựng video"))
    hint = DiscoveryHint(category="công nghệ", suggestion=as_suggestion(t, resolve_category(settings,"công nghệ"), []))
    settings.prompts_dir.mkdir()
    (settings.prompts_dir / "researcher.txt").write_text("Chỉ dùng nguồn gốc.", encoding="utf-8")
    llm = FakeLLM([json.dumps(data)])
    brief = create_brief("Dựng video", [source], llm, settings, JsonCache(settings.cache_dir), discovery_hint=hint)
    assert len(brief.facts) == 3 and all(str(f.source_url) == str(source.url) for f in brief.facts)
    assert "topic_inspiration_only" in llm.prompts[0] and "why_hot" in llm.prompts[0]


def test_scout_handoff_auto_category_and_history_after_completion(stages, monkeypatch):
    from pipeline.auto_category import run_auto
    from tests.test_run_all import state
    from tests.test_topic_discovery import suggestion
    settings, calls, _, _ = stages
    cfg = config()
    monkeypatch.setattr("pipeline.auto_category.load_trends", lambda s: cfg)
    scan = Mock(return_value={"category": "công nghệ", "topics": [suggestion()], "warnings": []})
    old = Mock()
    monkeypatch.setattr("pipeline.auto_category.scout", scan)
    monkeypatch.setattr("pipeline.auto_category.discover_topics", old)
    project = run_auto("công nghệ", settings=settings, duration=45, review=True)
    assert calls == ["research", "director"] and not Repository.for_settings(settings).recent_topics()
    assert state(project)["config"]["discovery"]["suggestion"]["why_now"] == suggestion()["why_now"]
    run_auto(resume=project, settings=settings)
    assert state(project)["status"] == "done" and len(Repository.for_settings(settings).recent_topics()) == 1
    assert (project / "trend_scout.json").exists()
    scan.assert_called_once()
    old.assert_not_called()


def test_empty_scout_uses_existing_news_discovery(stages, monkeypatch):
    from pipeline.auto_category import run_auto
    from tests.test_topic_discovery import suggestion
    settings, calls, _, _ = stages
    monkeypatch.setattr("pipeline.auto_category.load_trends", lambda s: config())
    monkeypatch.setattr("pipeline.auto_category.scout", Mock(return_value={"topics": [], "warnings": ["HTTP 429"]}))
    fallback = Mock(return_value={"topics": [suggestion()], "warnings": []})
    monkeypatch.setattr("pipeline.auto_category.discover_topics", fallback)
    project = run_auto("công nghệ", settings=settings, duration=45)
    fallback.assert_called_once()
    assert "render" in calls and "HTTP 429" in (project / "report.md").read_text(encoding="utf-8")


def test_cli_disabled_offline(settings, monkeypatch, capsys):
    from pipeline.trend_scout import main
    monkeypatch.setattr("pipeline.trend_scout.get_settings", lambda: settings)
    monkeypatch.setattr("sys.argv", ["trend_scout", "--category", "công nghệ"])
    assert main() == 0
    assert "đang tắt" in capsys.readouterr().out
    assert (settings.output_dir / "trend_scout_latest.json").exists()


def test_ui_manual_inspiration_goes_to_new_research_without_scan(settings, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr("config.settings.get_settings", lambda: settings)
    worker = Mock()
    worker.snapshot.return_value = None
    monkeypatch.setattr("app.views.trend_scout.scout_jobs", lambda: worker)
    app = AppTest.from_file(ROOT_DIR / "app/streamlit_app.py", default_timeout=30).run()
    app.sidebar.radio[0].set_value("Trend Scout").run()
    assert not app.exception
    app.text_area(key="trend_manual").input("Ngân hàng đổi cách bảo mật")
    next(b for b in app.button if b.label == "Đưa thẳng vào Researcher").click().run()
    assert not app.exception and app.sidebar.radio[0].value == "Research"
    assert app.text_input(key="research_topic_new").value == "Ngân hàng đổi cách bảo mật"
    worker.submit.assert_not_called()
