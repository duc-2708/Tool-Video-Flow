"""Source diagnosis, entities, HTML fallback and quota; all API calls mocked."""
import json
from unittest.mock import Mock
import pytest
import requests
from pydantic import SecretStr
from ddgs.exceptions import DDGSException
from agents.researcher import run_research,ResearchError
from agents.search_queries import generate_queries,entity_topics
from schemas.research_brief import SearchQuery
from config.settings import Settings
from sources.web_search import WebSearch,search_summary
from sources.youtube_trends import YouTubeTrends
from sources.youtube import QuotaExceeded
from utils.cache import JsonCache
from utils.diagnostics import Diagnostics
from utils.cache import write_json


def test_counts_include_every_url_and_reason(tmp_path,monkeypatch):
    settings = Settings(root_dir=tmp_path)
    search = WebSearch(settings,JsonCache(settings.cache_dir))
    rows = [{"href":f"https://example.com/{path}"} for path in ["category/ai","short","blocked","error","good","good"]]
    monkeypatch.setattr(search,"_search",lambda topic,kind,*args:rows if kind == "text" else [])
    def article(url):
        if url.endswith("blocked"):
            response = requests.Response()
            response.status_code = 403
            raise requests.HTTPError("fixture blocked",response=response)
        if url.endswith("error"):
            raise requests.Timeout("fixture timeout")
        return ("Valid article content. "*(16 if url.endswith("good") else 2),url,"2026-10-21")
    monkeypatch.setattr(search,"_article",article)
    docs,_ = search.collect("Test")
    report = search.summarize([str(source.url) for source in docs])
    assert report["found"] == 6 and report["kept"] == 1 and report["discarded"] == 5
    assert report["reasons"]["trùng nguồn"] == 1 and report["reasons"]["bị chặn"] == 1
    assert 300<=docs[0].content_length<500
    log = (settings.logs_dir/"researcher_errors.log").read_text(encoding="utf-8")
    assert "tìm được 6 kết quả" in log and all(row["href"] in log for row in rows)
    assert "quá ngắn" in log and "lỗi tải" in log
    assert "giữ 1 nguồn" in search_summary(report)


def test_raw_html_fallback_on_extractor_error(tmp_path,monkeypatch):
    settings = Settings(root_dir=tmp_path,retry_attempts=1)
    search = WebSearch(settings,JsonCache(settings.cache_dir))
    body = "Factual article paragraph for extraction. "*12
    html = ("<html><body><nav>Navigation</nav><article><p>"+body+"</p></article><script>bad()</script></body></html>").encode()
    monkeypatch.setattr("sources.web_search.ensure_public_url",lambda url:None)
    monkeypatch.setattr("sources.web_search.trafilatura.extract",Mock(side_effect=ValueError("fixture extraction failure")))
    response = Mock(status_code=200,headers={"Content-Type":"text/html"})
    response.iter_content.return_value = [html]
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    session = Mock()
    session.get.return_value = response
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    monkeypatch.setattr("sources.web_search.requests.Session",lambda:session)
    text,_,_ = search._article("https://example.com/article")
    assert len(text)>=300 and "Navigation" not in text and "bad()" not in text
    assert "HTML thô fallback" in (settings.logs_dir/"researcher_errors.log").read_text(encoding="utf-8")


def test_search_retry_waits_after_rate_limit(tmp_path,monkeypatch):
    settings = Settings(root_dir=tmp_path,retry_attempts=2)
    client = Mock()
    client.text.side_effect = [DDGSException("429 rate limited"),[]]
    monkeypatch.setattr("sources.web_search.DDGS",lambda **kwargs:client)
    sleep = Mock()
    monkeypatch.setattr("tenacity.nap.time.sleep",sleep)
    search = WebSearch(settings,JsonCache(settings.cache_dir))
    assert search._search("fixture","text",3) == []
    assert client.text.call_count == 2 and sleep.call_count == 1
    assert sleep.call_args.args[0]>=1


def test_entities_generate_separate_queries(tmp_path):
    settings = Settings(root_dir=tmp_path)
    provider = Mock(model_name="offline")
    provider.generate_json.return_value = json.dumps({"languages":[{"source_lang":"en","queries":["product alpha launch","product beta launch","product gamma launch"]}]})
    queries = generate_queries("Alpha, Beta và Gamma, Delta",["en"],provider,settings,JsonCache(settings.cache_dir),Diagnostics(settings.logs_dir))
    assert entity_topics("Alpha, Beta và Gamma, Delta") == ["Alpha","Beta","Gamma"]
    assert len(queries) == 3
    assert "mỗi truy vấn tập trung một thực thể" in provider.generate_json.call_args.args[0]


def test_no_sources_error_contains_counts_and_persisted_report(tmp_path,monkeypatch):
    settings = Settings(root_dir=tmp_path,gemini_model="offline",gemini_api_key=SecretStr("fixture-private"))
    provider = Mock(model_name="offline")
    monkeypatch.setattr("agents.researcher.GeminiProvider",lambda settings:provider)
    monkeypatch.setattr("agents.researcher.generate_queries",lambda *args:[SearchQuery(source_lang="vi",query="query fixture",region="vn-vi")])
    monkeypatch.setattr(WebSearch,"_search",lambda *args:[{"href":"https://example.com/category/news"}])
    with pytest.raises(ResearchError) as caught:
        run_research("test",settings,use_youtube=False,output_dir=tmp_path/"project",progress=lambda _:None)
    message = str(caught.value)
    assert "tìm được 2 kết quả" in message and "giữ 0 nguồn" in message and "loại 2 nguồn" in message
    assert "rút gọn chủ đề" in message and "tăng số nguồn" in message
    report = json.loads((tmp_path/"project/sources.json").read_text(encoding="utf-8"))
    assert report["search_diagnostics"]["found"] == 2
    provider.generate_json.assert_not_called()
    provider.close.assert_called_once()


def test_youtube_retry_cost_and_quota_warning(tmp_path,monkeypatch):
    settings = Settings(root_dir=tmp_path,youtube_api_key=SecretStr("fixture-private"),retry_attempts=2,youtube_max_searches_per_run=3)
    source = YouTubeTrends(settings,JsonCache(settings.cache_dir))
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.json.return_value = {"items":[]}
    response.raise_for_status.side_effect = [requests.Timeout("fixture timeout"),None,None,None]
    monkeypatch.setattr("sources.youtube.requests.get",Mock(return_value=response))
    monkeypatch.setattr("tenacity.nap.time.sleep",lambda _:None)
    source._request("search",{"q":"fixture"})
    source._request("videos",{})
    source._request("commentThreads",{})
    ledger = json.loads((settings.cache_dir/"youtube_quota.json").read_text())
    assert ledger["estimated_units"] == 202 and ledger["search_calls"] == 2
    limited = YouTubeTrends(settings.model_copy(update={"youtube_daily_quota":202}),JsonCache(settings.cache_dir))
    with pytest.raises(QuotaExceeded,match="YOUTUBE_DAILY_QUOTA"):
        limited._request("videos",{})
    assert "Cảnh báo quota" in (settings.logs_dir/"researcher_errors.log").read_text(encoding="utf-8")


def test_ui_displays_search_diagnostics_even_without_brief(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from config.settings import ROOT_DIR
    from pipeline.projects import create_project
    settings = Settings(root_dir=tmp_path)
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    project = create_project(settings.output_dir,"Chẩn đoán nguồn")
    write_json(project/"sources.json",{"sources":[],"search_diagnostics":{"found":4,"kept":0,"discarded":4,
        "reasons":{"quá ngắn":4},"queries":[]}})
    app = AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=25).run()
    app.sidebar.radio[0].set_value("Research").run()
    assert not app.exception
    assert any("tìm được 4 kết quả, giữ 0 nguồn, loại 4 nguồn" in item.value for item in app.info)


def test_ui_warns_when_three_grounded_facts_remain(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from config.settings import ROOT_DIR
    from pipeline.projects import create_project
    from tests.test_researcher import response_data
    from tests.test_multilingual import english_source
    settings = Settings(root_dir=tmp_path)
    monkeypatch.setattr("config.settings.get_settings",lambda:settings)
    project = create_project(settings.output_dir,"Dữ liệu mỏng")
    write_json(project/"brief.json",response_data(english_source()))
    app = AppTest.from_file(ROOT_DIR/"app/streamlit_app.py",default_timeout=25).run()
    app.sidebar.radio[0].set_value("Research").run()
    assert not app.exception
    assert any(item.value == "dữ liệu mỏng, kịch bản sẽ ít chi tiết" for item in app.warning)
