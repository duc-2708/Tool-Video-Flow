"""Official API metadata/comments only. No downloads, captions or transcripts."""
from datetime import datetime,timedelta,timezone
import html
import json
import re
import requests
from pydantic import ValidationError
from schemas.research_brief import TrendSignal
from sources.youtube import YouTubeSource,QuotaExceeded
from utils.diagnostics import Diagnostics
from utils.text import clean_text


class YouTubeTrends(YouTubeSource):
    def __init__(self,settings,cache,diagnostics=None):
        super().__init__(settings,cache,transcripts=None)
        self.diagnostics = diagnostics or Diagnostics(settings.logs_dir,filename="researcher_errors.log",
            secrets=[settings.youtube_api_key.get_secret_value()])
        key = settings.youtube_api_key.get_secret_value()
        if key and key not in self.diagnostics.secrets:
            self.diagnostics.secrets.append(key)
        self.units_reserved = 0

    def _reserve(self,cost,search):
        cost = 100 if search else cost
        try:
            super()._reserve(cost,search)
        except QuotaExceeded as error:
            self.diagnostics.record_exception(error,f"Cảnh báo quota: yêu cầu +{cost} đơn vị bị chặn; YOUTUBE_DAILY_QUOTA={self.settings.youtube_daily_quota}")
            raise
        self.units_reserved += cost
        state = json.loads((self.settings.cache_dir/"youtube_quota.json").read_text(encoding="utf-8"))
        self.diagnostics.record(f"YouTube trends quota local: +{cost}, reserved_this_run={self.units_reserved}, search_this_run={self.searches_this_run}; estimated_daily_units={state['estimated_units']}, daily_search_calls={state['search_calls']}, daily cap={self.settings.youtube_daily_quota}. Các lần retry cũng được tính.")

    def _request(self,endpoint,params):
        try:
            return super()._request(endpoint,params)
        except Exception as error:
            self.diagnostics.record_exception(error,f"YouTube trends API {endpoint}")
            raise

    @staticmethod
    def quota_error(error):
        if isinstance(error,QuotaExceeded):
            return True
        if isinstance(error,requests.HTTPError) and error.response is not None:
            try:
                reasons = error.response.json().get("error",{}).get("errors",[])
                return any(row.get("reason") in {"quotaExceeded","dailyLimitExceeded","rateLimitExceeded"} for row in reasons)
            except (ValueError,AttributeError,TypeError):
                pass
        return False

    def collect(self,topic,limit=5,*,days=14,vietnamese=True,now=None):
        if type(days) is not int or not 1 <= days <= 3650 or not 1 <= limit <= 10:
            raise ValueError("YouTube trends cần 1–10 video và khoảng thời gian 1–3650 ngày.")
        if not self.settings.youtube_api_key.get_secret_value().strip():
            return [],["Thiếu YOUTUBE_API_KEY; bỏ qua YouTube trends, vẫn tiếp tục Research bằng web."]
        current = now or datetime.now(timezone.utc)
        cutoff = current-timedelta(days=days)
        inputs = {"topic":clean_text(topic),"limit":limit,"days":days,"vietnamese":vietnamese,"as_of_day":current.date().isoformat()}
        params = {"part":"snippet","q":inputs["topic"],"type":"video","order":"viewCount","maxResults":limit,
            "publishedAfter":cutoff.isoformat().replace("+00:00","Z"),"safeSearch":"moderate"}
        if vietnamese:
            params.update(regionCode="VN",relevanceLanguage="vi")
        warnings = []
        try:
            ids = self.cache.get("youtube-trends-search-v1",inputs)
            if not isinstance(ids,list):
                raw = self._request("search",params)
                ids = list(dict.fromkeys(item.get("id",{}).get("videoId","") for item in raw.get("items",[])))
                ids = [value for value in ids if isinstance(value,str) and re.fullmatch(r"[A-Za-z0-9_-]{11}",value)][:limit]
                self.cache.set("youtube-trends-search-v1",inputs,ids)
            if not ids:
                return [],["Không tìm thấy video YouTube trong khoảng ngày đã chọn; chỉ dùng nguồn web cho facts."]
            items = self.cache.get("youtube-trends-details-v1",{"ids":ids})
            if not isinstance(items,list):
                raw = self._request("videos",{"part":"snippet,statistics,contentDetails","id":",".join(ids)})
                items = raw.get("items",[])
                self.cache.set("youtube-trends-details-v1",{"ids":ids},items)
        except Exception as error:
            self.diagnostics.record_exception(error,"Bỏ qua YouTube trends do API/quota/cache lỗi")
            return [],["YouTube trends không khả dụng hoặc hết quota; tiếp tục Research bằng nguồn web."]
        signals = []
        for item in items:
            try:
                if item.get("id") not in ids:
                    continue
                snippet = item.get("snippet",{})
                published = snippet["publishedAt"]
                when = datetime.fromisoformat(published.replace("Z","+00:00"))
                if when.tzinfo is None or not cutoff <= when <= current:
                    continue
                stats = item.get("statistics",{})
                def count(name):
                    value = stats.get(name)
                    return int(value) if str(value).isdigit() else None
                tags = re.findall(r"#[\w]+",snippet.get("title","")+" "+snippet.get("description",""))
                signals.append(TrendSignal(title=html.unescape(snippet["title"]),channel=html.unescape(snippet["channelTitle"]),
                    url="https://www.youtube.com/watch?v="+item["id"],views=count("viewCount"),likes=count("likeCount"),comments=count("commentCount"),
                    published_at=published,hashtags=list(dict.fromkeys(tags))[:30]))
            except (KeyError,AttributeError,TypeError,ValueError,ValidationError) as error:
                self.diagnostics.record_exception(error,"Bỏ một metadata video YouTube không hợp lệ")
                warnings.append("Một video có metadata không hợp lệ đã bị bỏ qua.")
        signals.sort(key=lambda signal:signal.views if signal.views is not None else -1,reverse=True)
        for signal in signals[:3]:
            video_id = str(signal.url).split("v=",1)[1]
            try:
                comments = self.cache.get("youtube-trends-comments-v1",{"id":video_id})
                if not isinstance(comments,dict):
                    raw = self._request("commentThreads",{"part":"snippet","videoId":video_id,"order":"relevance","maxResults":10,"textFormat":"plainText"})
                    texts = []
                    for row in raw.get("items",[])[:10]:
                        snippet = row.get("snippet",{}).get("topLevelComment",{}).get("snippet",{})
                        text = clean_text(html.unescape(snippet.get("textOriginal") or snippet.get("textDisplay") or ""))[:2000]
                        if text:
                            texts.append(text)
                    comments = {"texts":texts}
                    self.cache.set("youtube-trends-comments-v1",{"id":video_id},comments)
                signal.top_comments = comments["texts"][:10]
            except Exception as error:
                self.diagnostics.record_exception(error,"Không lấy được bình luận YouTube; giữ metadata")
                warnings.append("Một số bình luận YouTube không khả dụng hoặc hết quota; vẫn giữ metadata video.")
                if self.quota_error(error):
                    break
        self.diagnostics.record(f"YouTube trends: {len(signals)} video, {sum(len(signal.top_comments) for signal in signals)} bình luận; quota local đã đặt trước trong lượt={self.units_reserved}.")
        return signals,list(dict.fromkeys(warnings))
