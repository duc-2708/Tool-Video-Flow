"""Official videos.list chart=mostPopular; shared quota including every retry."""
from schemas.trends import Metrics, TrendItem
from sources.youtube import YouTubeSource
from providers.trends.base import BaseProvider, count, short_text

CATEGORY_IDS = {"tin-tuc": "25", "cong-nghe": "28", "giai-tri": "24", "the-thao": "17", "game": "20", "du-lich": "19"}


class YouTubeTrending(BaseProvider):
    name = "youtube_trending"

    def _fetch(self, category, limit):
        if not self.settings.youtube_api_key.get_secret_value().strip():
            self.warn("Thiếu YOUTUBE_API_KEY; bỏ qua.")
            return []
        def load():
            source = YouTubeSource(self.settings, self.cache)
            params = {"part": "snippet,statistics", "chart": "mostPopular", "regionCode": self.region, "maxResults": min(50, limit*2)}
            if category.category_id in CATEGORY_IDS:
                params["videoCategoryId"] = CATEGORY_IDS[category.category_id]
            raw = source._request("videos", params)
            self.diagnostics.record("Trend Scout YouTube videos.list: 1 quota đơn vị mỗi HTTP attempt; ledger dùng chung.")
            result = []
            for row in raw.get("items") or []:
                import re
                identity = str(row.get("id") or "")
                if not re.fullmatch(r"[\w-]{11}", identity, flags=re.ASCII):
                    continue
                snippet, stats = row.get("snippet") or {}, row.get("statistics") or {}
                title = short_text(snippet.get("title"), 240)
                if not title or (category.category_id not in CATEGORY_IDS and not self.relevant(title, category)):
                    continue
                result.append(TrendItem(id=identity, title=title, summary=short_text(snippet.get("description"), 300),
                    url="https://www.youtube.com/watch?v="+identity, platform="youtube", region=self.region,
                    language=str(snippet.get("defaultLanguage") or "und"), score_raw=count(stats.get("viewCount")),
                    metrics=Metrics(views=count(stats.get("viewCount")), likes=count(stats.get("likeCount")), comments=count(stats.get("commentCount")))))
            return result
        return self.cached([category.category_id, limit], load)
