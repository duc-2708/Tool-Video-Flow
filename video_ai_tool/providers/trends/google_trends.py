"""Google Trending Now RSS (daily-style feed), skipped if endpoint unavailable."""
from urllib.parse import quote
import feedparser
from schemas.trends import Metrics, TrendItem
from providers.trends.base import BaseProvider, count, short_text


class GoogleTrends(BaseProvider):
    name = "google_trends"

    def _fetch(self, category, limit):
        def load():
            text = self.request("https://trends.google.com/trending/rss", {"geo": self.region}, text=True)
            feed = feedparser.parse(text)
            if not feed.entries:
                raise ValueError("RSS Google Trends không có mục hoặc không truy cập được.")
            result = []
            for row in feed.entries[:100]:
                title = short_text(row.get("title"), 240)
                if not title or not self.relevant(title, category):
                    continue
                traffic = count(str(row.get("ht_approx_traffic") or "0").replace(",", "").replace("+", ""))
                result.append(TrendItem(id=title, title=title, platform="google_trends", region=self.region,
                    language="vi" if self.region == "VN" else "und", score_raw=traffic, metrics=Metrics(views=traffic),
                    url=f"https://trends.google.com/trends/explore?geo={self.region}&q={quote(title)}"))
            return result[:limit]
        return self.cached([category.category_id, limit], load)
