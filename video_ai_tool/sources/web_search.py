# file: sources/web_search.py
"""DDGS text/news + trafilatura; chỉ tải HTML, không tải ảnh/video xã hội."""
from datetime import datetime, timezone
import ipaddress
import socket
import re
from urllib.parse import urljoin, urlsplit
from typing import Any
import requests
import trafilatura
from ddgs import DDGS
from ddgs.exceptions import DDGSException
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential_jitter
from config.settings import Settings
from schemas.source import SourceDocument
from utils.cache import JsonCache
from utils.retry import network_retry
from utils.text import clean_text
from schemas.languages import REGIONS
from utils.source_credits import publisher_name
from utils.diagnostics import Diagnostics
from collections import Counter
from lxml import html as html_parser


def raw_article_text(html):
    """Fallback from already downloaded HTML; never use search snippets."""
    root = html_parser.fromstring(html)
    for node in root.xpath("//script|//style|//nav|//header|//footer|//aside|//form"):
        node.drop_tree()
    containers = root.xpath("//article|//main")
    container = containers[0] if containers else root
    paragraphs = container.xpath(".//p|.//h1|.//h2")
    return article_excerpt("\n\n".join(node.text_content() for node in paragraphs))


def search_summary(report):
    reasons = ", ".join(f"{key}: {value}" for key,value in report.get("reasons",{}).items())
    return (f"tìm được {report.get('found',0)} kết quả, giữ {report.get('kept',0)} nguồn, "
        f"loại {report.get('discarded',0)} nguồn"+(f" ({reasons})" if reasons else ""))


def retry_search(error):
    response = getattr(error,"response",None)
    return isinstance(error,(DDGSException,requests.Timeout,requests.ConnectionError)) or (
        isinstance(error,requests.HTTPError) and response is not None and response.status_code in (429,503))

SOCIAL_HOSTS = ("youtube.com", "youtu.be", "tiktok.com", "facebook.com", "fb.watch", "instagram.com")
MAX_HTML_BYTES = 2_000_000


def article_excerpt(text,limit=8000):
    """Preserve paragraph boundaries; never cut halfway through a paragraph."""
    paragraphs = [clean_text(part) for part in re.split(r"\n+",text) if clean_text(part)]
    result = []
    length = 0
    for paragraph in paragraphs:
        if length+len(paragraph)+(2 if result else 0)>limit:
            break
        result.append(paragraph)
        length += len(paragraph)+(2 if len(result)>1 else 0)
    return "\n\n".join(result)


def article_url(url):
    if not allowed_web_url(url):
        return False
    path = urlsplit(url).path.strip("/").lower()
    return bool(path) and path not in {"news","world","technology","tech","business","latest","home","index.html","the-gioi","thoi-su","kinh-doanh","cong-nghe","giai-tri"} and not re.match(r"^(?:category|categories|tag|tags|topics|author|search)(?:/|$)",path)


def allowed_web_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().rstrip(".")
        return (parts.scheme in {"http", "https"} and bool(host) and not parts.username
                and not parts.password and parts.port in {None, 80, 443}
                and not any(host == domain or host.endswith("." + domain) for domain in SOCIAL_HOSTS))
    except ValueError:
        return False


def ensure_public_url(url: str) -> None:
    if not allowed_web_url(url):
        raise ValueError("Không phải URL bài viết web được phép.")
    host = urlsplit(url).hostname
    addresses = socket.getaddrinfo(host, None)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("Không truy cập địa chỉ mạng nội bộ.")


class WebSearch:
    def __init__(self, settings: Settings, cache: JsonCache) -> None:
        self.settings, self.cache = settings, cache
        self.article_metadata = {}
        self.diagnostics = Diagnostics(settings.logs_dir)
        self.search_report = {"queries":[],"found":0,"kept":0,"discarded":0,"reasons":{}}

    def summarize(self,selected_urls=None):
        decisions = [row for query in self.search_report["queries"] for row in query["decisions"]]
        selected = set(selected_urls) if selected_urls is not None else None
        seen = set()
        for row in decisions:
            if not row["kept"]:
                continue
            url = row.get("final_url") or row["url"]
            reason = "trùng nguồn" if url in seen else "ngoài giới hạn số nguồn" if selected is not None and url not in selected else None
            if reason:
                row.update(kept=False,reason=reason)
                self.diagnostics.record(f"URL {row['url']}: loại — {reason}")
            else:
                seen.add(url)
        kept = sum(row["kept"] for row in decisions)
        self.search_report.update(found=len(decisions),kept=kept,discarded=len(decisions)-kept,
            reasons=dict(Counter(row["reason"] for row in decisions if not row["kept"])))
        for query in self.search_report["queries"]:
            query["kept"] = sum(row["kept"] for row in query["decisions"])
            query["discarded"] = len(query["decisions"])-query["kept"]
        return self.search_report

    def _search(self, topic: str, kind: str, limit: int, source_lang="vi") -> list[dict[str, Any]]:
        region = REGIONS[source_lang]
        inputs = {"topic": topic, "kind": kind, "limit": limit, "region": region}
        cached = self.cache.get("ddgs-v1", inputs)
        if isinstance(cached, list):
            return cached
        results: list[dict[str, Any]] = []
        for attempt in Retrying(retry=retry_if_exception(retry_search),
                                stop=stop_after_attempt(self.settings.retry_attempts),
                                wait=wait_exponential_jitter(initial=1, max=30), reraise=True,
                                before_sleep=lambda state:self.diagnostics.record_exception(state.outcome.exception(),
                                    f"DDGS chờ {state.next_action.sleep:.1f}s trước retry {state.attempt_number+1}: {topic}")):
            with attempt:
                client = DDGS(timeout=int(self.settings.request_timeout_sec))
                search = client.news if kind == "news" else client.text
                results = list(search(topic, region=region, safesearch="moderate", max_results=limit))
                for row in results:
                    row["_retrieved_at"] = datetime.now(timezone.utc).isoformat()
        self.cache.set("ddgs-v1", inputs, results)
        return results

    def _article(self, url: str) -> tuple[str, str, str]:
        callback=getattr(self,"progress",None)
        if callback: callback("Đang đọc nguồn: "+url)
        cached = self.cache.get("article-deep-v3", {"url": url})
        if isinstance(cached, dict) and len(cached.get("text",""))>=300:
            self.article_metadata[cached["url"]] = cached.get("metadata",{})
            return cached["text"], cached["url"], cached["retrieved_at"]

        @network_retry(self.settings.retry_attempts)
        def download() -> tuple[str, str, str]:
            current = url
            with requests.Session() as session:
                for _ in range(4):
                    ensure_public_url(current)
                    with session.get(current, timeout=self.settings.request_timeout_sec, stream=True,
                                     allow_redirects=False, headers={"User-Agent": "video_ai_tool/0.2 (research)"}) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            current = urljoin(current, response.headers.get("Location", ""))
                            continue
                        response.raise_for_status()
                        if "text/html" not in response.headers.get("Content-Type", "").lower():
                            raise ValueError("Nguồn không phải HTML.")
                        chunks, total = [], 0
                        for chunk in response.iter_content(65536):
                            total += len(chunk)
                            if total > MAX_HTML_BYTES:
                                raise ValueError("Bài viết vượt giới hạn tải.")
                            chunks.append(chunk)
                        html = b"".join(chunks)
                        try:
                            metadata = trafilatura.extract_metadata(html, default_url=current)
                        except Exception:
                            metadata = None
                        lang = re.search(rb'<html\b[^>]*\blang\s*=\s*["\']([a-zA-Z-]+)',html[:10000],re.I)
                        self.article_metadata[current] = {"published_at":getattr(metadata,"date",None),
                            "source_name":clean_text(getattr(metadata,"sitename",None) or "")[:120],
                            "source_lang":lang.group(1).decode("ascii").lower().split("-")[0] if lang else None}
                        try:
                            extracted = trafilatura.extract(html, url=current,
                                include_comments=False, include_tables=True, include_images=False,
                                favor_precision=True, max_tree_size=200000)
                        except Exception as error:
                            self.diagnostics.record_exception(error,f"Trích xuất thất bại, thử HTML thô {current}")
                            extracted = None
                        text = article_excerpt(extracted or "")
                        if len(text)<300:
                            fallback = raw_article_text(html)
                            if len(fallback)>len(text):
                                text = fallback
                                self.diagnostics.record(f"HTML thô fallback {current}: {len(text)} ký tự")
                        if not text:
                            raise ValueError("Không trích xuất được nội dung bài viết.")
                        return text, current, datetime.now(timezone.utc).isoformat()
            raise ValueError("Nguồn chuyển hướng quá nhiều lần.")

        text, final_url, retrieved_at = download()
        self.cache.set("article-deep-v3", {"url": url}, {"text": text, "url": final_url, "retrieved_at": retrieved_at,"metadata":self.article_metadata.get(final_url,{})})
        return text, final_url, retrieved_at

    def collect(self, topic: str, limit: int = 6, source_lang="vi") -> tuple[list[SourceDocument], list[str]]:
        if not 1 <= limit <= 12:
            raise ValueError("Số nguồn web phải từ 1 đến 12.")
        rows: list[dict[str, Any]] = []
        warnings: list[str] = []
        record = {"query":topic,"source_lang":source_lang,"decisions":[],"found":0,"search_errors":[]}
        self.search_report["queries"].append(record)
        for kind in ("text", "news"):
            try:
                results = self._search(topic, kind, limit, source_lang)
                rows.extend(results)
                self.diagnostics.record(f"Truy vấn [{source_lang}/{kind}] {topic}: tìm được {len(results)} kết quả")
            except Exception as error:
                record["search_errors"].append(kind+": "+type(error).__name__)
                self.diagnostics.record_exception(error,f"Truy vấn [{source_lang}/{kind}] {topic}: tìm được 0 kết quả, lỗi tìm kiếm")
                warnings.append(f"Tìm web/{kind} không khả dụng; đã dùng các nguồn còn lại.")
        documents: list[SourceDocument] = []
        seen: set[str] = set()
        record["found"] = len(rows)
        def decide(url,kept,reason,final_url=None):
            record["decisions"].append({"url":url,"kept":kept,"reason":reason,"final_url":final_url})
            self.diagnostics.record(f"URL {url}: {'giữ' if kept else 'loại'} — {reason}")
        from agents.explainer_research import live_blog
        for row in sorted(rows,key=lambda item:(live_blog(item.get("href") or item.get("url") or "",item.get("title", "")),not bool(item.get("date")))):
            url = str(row.get("href") or row.get("url") or "")
            if url in seen or not article_url(url):
                decide(url,False,"trùng nguồn" if url in seen else "trang chuyên mục/trang chủ" if allowed_web_url(url) else "URL bị chặn/không hợp lệ")
                if url not in seen:
                    warnings.append("Bỏ URL không phải bài viết cụ thể hoặc là trang chuyên mục/trang chủ.")
                continue
            seen.add(url)
            if len(documents)>=limit:
                decide(url,False,"ngoài giới hạn số nguồn")
                continue
            kind = "article"
            try:
                text, final_url, retrieved_at = self._article(url)
            except Exception as error:
                response = getattr(error,"response",None)
                blocked = response is not None and response.status_code in (401,403,429)
                decide(url,False,"bị chặn" if blocked else "lỗi tải/trích xuất")
                self.diagnostics.record_exception(error,f"Đọc bài {url}")
                warnings.append("Bỏ nguồn không đọc được bài đầy đủ; không dùng snippet tìm kiếm làm fact.")
                continue
            text = article_excerpt(text)
            if len(text)<300:
                decide(url,False,f"quá ngắn (<300 ký tự)")
                warnings.append(f"Bỏ bài quá ngắn: {len(text)} ký tự, yêu cầu ít nhất 300 ký tự.")
                continue
            if not text or not article_url(final_url) or final_url in {str(doc.url) for doc in documents}:
                decide(url,False,"trùng nguồn" if final_url in {str(doc.url) for doc in documents} else "trang chuyên mục/trang chủ sau chuyển hướng")
                continue
            try:
                host = urlsplit(final_url).hostname or "web"
                name = publisher_name(final_url)
                if name == host.removeprefix("www."):
                    name = self.article_metadata.get(final_url,{}).get("source_name") or name
                documents.append(SourceDocument(title=clean_text(str(row.get("title") or "Nguồn web")),
                    url=final_url, source_name=name, platform="web",
                    text=text, retrieved_at=retrieved_at,
                    source_lang=self.article_metadata.get(final_url,{}).get("source_lang") if self.article_metadata.get(final_url,{}).get("source_lang") in REGIONS else source_lang,
                    published_at=self.article_metadata.get(final_url,{}).get("published_at") or (str(row["date"]) if row.get("date") else None), content_kind=kind))
            except ValueError:
                decide(url,False,"metadata nguồn không hợp lệ")
                continue
            decide(url,True,f"bài đầy đủ {len(text)} ký tự",final_url)
        summary = self.summarize()
        self.diagnostics.record(f"Tổng truy vấn {topic}: "+search_summary(summary))
        return documents, list(dict.fromkeys(warnings))


if __name__ == "__main__":
    from sources.debug import run_debug
    raise SystemExit(run_debug("web"))
