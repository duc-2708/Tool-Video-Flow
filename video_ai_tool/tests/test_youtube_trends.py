"""Official YouTube API mocked throughout; never use a real key or quota."""
from datetime import datetime,timedelta,timezone
import json
from unittest.mock import Mock
import pytest
import requests
from pydantic import SecretStr
from config.settings import ROOT_DIR,Settings
from sources.youtube_trends import YouTubeTrends
from schemas.research_brief import ResearchBrief,TrendSignal,TrendInsights
from agents.trend_insights import summarize_trends
from agents.researcher import run_research
from utils.cache import JsonCache
from utils.diagnostics import Diagnostics
from tests.test_researcher import response_data, fake_queries

NOW = datetime(2026,10,20,12,tzinfo=timezone.utc)
IDS = ["video000001","video000002","video000003","video000004"]


@pytest.fixture
def settings(tmp_path):
    return Settings(root_dir=tmp_path,youtube_api_key=SecretStr("fixture-youtube-secret"),retry_attempts=1)


def details(index):
    return {"id":IDS[index],"snippet":{"title":f"Hook dựng video {index} #CapCut","channelTitle":f"Kênh {index}",
            "description":"Góc dựng #EditVideo","publishedAt":(NOW-timedelta(days=2)).isoformat()},
            "statistics":{"viewCount":str((index+1)*100),"likeCount":"12","commentCount":"8"},"contentDetails":{"duration":"PT40S"}}


def install_api(monkeypatch,*,fail=None):
    calls = []
    def get(url,**kwargs):
        endpoint = url.rsplit("/",1)[-1]
        calls.append((endpoint,kwargs))
        response = Mock()
        response.status_code = 200
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        if fail and endpoint == fail:
            error_response = requests.Response()
            error_response.status_code = 403
            error_response._content = b'{"error":{"errors":[{"reason":"quotaExceeded"}]}}'
            response.raise_for_status.side_effect = requests.HTTPError("fixture-youtube-secret quota error",response=error_response)
        if endpoint == "search":
            response.json.return_value = {"items":[{"id":{"videoId":video}} for video in IDS]}
        elif endpoint == "videos":
            response.json.return_value = {"items":[details(i) for i in range(4)]}
        elif endpoint == "commentThreads":
            response.json.return_value = {"items":[{"snippet":{"topLevelComment":{"snippet":{"textOriginal":"Dựng video bắt đầu từ đâu?"}}}} for _ in range(12)]}
        else:
            raise AssertionError("Không được gọi API khác, tải video hoặc transcript")
        return response
    monkeypatch.setattr("sources.youtube.requests.get",get)
    return calls


def test_search_parameters_top_three_comments_and_cache(settings,monkeypatch):
    calls = install_api(monkeypatch)
    cache = JsonCache(settings.cache_dir,settings.cache_ttl_sec)
    source = YouTubeTrends(settings,cache)
    signals,warnings = source.collect("Dựng video",4,now=NOW)
    assert not warnings and len(signals) == 4
    assert [s.views for s in signals] == [400,300,200,100]
    assert [len(s.top_comments) for s in signals] == [10,10,10,0]
    search = calls[0][1]["params"]
    assert search["order"] == "viewCount" and search["type"] == "video"
    assert search["regionCode"] == "VN" and search["relevanceLanguage"] == "vi"
    assert datetime.fromisoformat(search["publishedAfter"].replace("Z","+00:00")) == NOW-timedelta(days=14)
    assert calls[1][1]["params"]["part"] == "snippet,statistics,contentDetails"
    comments = [(endpoint,kwargs) for endpoint,kwargs in calls if endpoint == "commentThreads"]
    assert len(comments) == 3 and comments[0][1]["params"]["videoId"] == IDS[3]
    assert all(kwargs["params"]["order"] == "relevance" and kwargs["params"]["maxResults"] == 10 for _,kwargs in comments)
    assert all("key" not in kwargs["params"] for _,kwargs in calls)
    assert signals[0].hashtags == ["#CapCut","#EditVideo"]
    ledger = json.loads((settings.cache_dir/"youtube_quota.json").read_text(encoding="utf-8"))
    assert ledger["estimated_units"] == 104 and ledger["search_calls"] == 1
    assert "estimated_daily_units=104" in (settings.logs_dir/"researcher_errors.log").read_text(encoding="utf-8")
    assert YouTubeTrends(settings,cache).collect("Dựng video",4,now=NOW)[0] == signals
    assert len(calls) == 5


def test_international_search_omits_vietnam_filter(settings,monkeypatch):
    calls = install_api(monkeypatch)
    YouTubeTrends(settings,JsonCache(settings.cache_dir)).collect("AI",4,days=7,vietnamese=False,now=NOW)
    assert "regionCode" not in calls[0][1]["params"] and "relevanceLanguage" not in calls[0][1]["params"]


@pytest.mark.parametrize("setting",[{"youtube_max_searches_per_run":0},{"youtube_daily_quota":1}])
def test_quota_fallback_never_exceeds_budget(settings,setting,monkeypatch):
    calls = install_api(monkeypatch)
    source = YouTubeTrends(settings.model_copy(update=setting),JsonCache(settings.cache_dir))
    signals,warnings = source.collect("AI",now=NOW)
    assert not signals and warnings
    assert len(calls) <= (1 if "youtube_daily_quota" in setting else 0)


def test_api_quota_error_is_redacted_and_does_not_raise(settings,monkeypatch):
    calls = install_api(monkeypatch,fail="search")
    signals,warnings = YouTubeTrends(settings,JsonCache(settings.cache_dir)).collect("AI",now=NOW)
    assert not signals and warnings and len(calls) == 1
    text = (settings.logs_dir/"researcher_errors.log").read_text(encoding="utf-8")
    assert "Traceback" in text and "fixture-youtube-secret" not in text


def test_comment_quota_error_preserves_metadata_and_stops_requests(settings,monkeypatch):
    calls = install_api(monkeypatch,fail="commentThreads")
    signals,warnings = YouTubeTrends(settings,JsonCache(settings.cache_dir)).collect("AI",4,now=NOW)
    assert len(signals) == 4 and warnings and len(calls) == 3
    assert all(not signal.top_comments for signal in signals)


def signal_fixture():
    return TrendSignal(title="Bắt đầu dựng video thế nào?",channel="Fixture",url="https://www.youtube.com/watch?v="+IDS[0],
        views=100,likes=None,comments=1,published_at="2026-10-19T00:00:00Z",top_comments=["Bắt đầu từ đâu?"])


def insight_fixture():
    return {"hook_patterns":[{"text":"Mở bằng câu hỏi bắt đầu từ đâu","reason":"Tiêu đề và bình luận đều hỏi cách bắt đầu","evidence_urls":[str(signal_fixture().url)]}],
            "keywords":[],"common_questions":[],"angles":[]}


def prepare_prompts(settings):
    settings.prompts_dir.mkdir(exist_ok=True)
    for name in ("researcher.txt","trend_insights.txt"):
        (settings.prompts_dir/name).write_text((ROOT_DIR/"prompts"/name).read_text(encoding="utf-8"),encoding="utf-8")


def test_gemini_insights_cached_with_reasons_and_refs(settings):
    prepare_prompts(settings)
    provider = Mock(model_name="fixture")
    provider.generate_json.return_value = json.dumps(insight_fixture())
    cache = JsonCache(settings.cache_dir)
    diagnostics = Diagnostics(settings.logs_dir)
    insights,warnings = summarize_trends([signal_fixture()],provider,settings,cache,diagnostics)
    assert not warnings and insights.hook_patterns[0].reason
    assert summarize_trends([signal_fixture()],provider,settings,cache,diagnostics)[0] == insights
    provider.generate_json.assert_called_once()
    assert "KHÔNG TIN CẬY" in provider.generate_json.call_args.args[0]


def test_gemini_insight_error_is_optional(settings):
    prepare_prompts(settings)
    provider = Mock(model_name="fixture")
    provider.generate_json.side_effect = ValueError("Fixture JSON lỗi")
    insights,warnings = summarize_trends([signal_fixture()],provider,settings,JsonCache(settings.cache_dir),Diagnostics(settings.logs_dir))
    assert not insights.hook_patterns and warnings


def test_invented_insight_url_not_accepted(settings):
    prepare_prompts(settings)
    data = insight_fixture()
    data["hook_patterns"][0]["evidence_urls"] = ["https://invented.example/video"]
    provider = Mock(model_name="fixture")
    provider.generate_json.return_value = json.dumps(data)
    insights,warnings = summarize_trends([signal_fixture()],provider,settings,JsonCache(settings.cache_dir),Diagnostics(settings.logs_dir))
    assert not insights.hook_patterns and warnings


@pytest.mark.parametrize("trends_fail",[False,True])
def test_research_facts_stay_web_and_trend_failure_nonfatal(settings,monkeypatch,trends_fail):
    from schemas.source import SourceDocument
    import agents.researcher as researcher
    settings = settings.model_copy(update={"gemini_api_key":SecretStr("fixture-gemini"),"gemini_model":"fixture"})
    prepare_prompts(settings)
    source = SourceDocument(title="Web",url="https://example.com/article",source_name="example.com",platform="web",content_kind="article",
        text="Dữ liệu này chỉ là ví dụ phục vụ kiểm thử phần mềm.",retrieved_at="2026-10-20T00:00:00Z")
    monkeypatch.setattr(researcher.WebSearch,"collect",lambda *args:([source],[]))
    monkeypatch.setattr(researcher,"generate_queries",fake_queries)
    collector = Mock()
    if trends_fail:
        collector.collect.side_effect = RuntimeError("Fixture quota error")
    else:
        collector.collect.return_value = ([signal_fixture()],[])
    monkeypatch.setattr(researcher,"YouTubeTrends",lambda *args:collector)
    provider = Mock(model_name="fixture")
    def generate(prompt,schema):
        if schema is ResearchBrief:
            assert "Bắt đầu dựng video thế nào?" not in prompt
            return json.dumps(response_data(source))
        assert schema is TrendInsights
        return json.dumps(insight_fixture())
    provider.generate_json.side_effect = generate
    monkeypatch.setattr(researcher,"provider_for_step",lambda *args,**kwargs:provider)
    monkeypatch.setattr("sources.transcripts.YouTubeTranscriptProvider.fetch",Mock(side_effect=AssertionError("Không được tải transcript")))
    path = run_research("Dựng video",settings,use_youtube=True,use_transcripts=True,progress=lambda message:None)
    brief = ResearchBrief.model_validate_json(path.read_text(encoding="utf-8"))
    assert len(brief.facts) == 3 and all(str(fact.source_url).startswith("https://example.com/") for fact in brief.facts)
    if trends_fail:
        assert not brief.trend_signals and any("YouTube trends" in warning for warning in brief.risks)
    else:
        assert len(brief.trend_signals) == 1 and brief.trend_insights.hook_patterns
    provider.close.assert_called_once()
