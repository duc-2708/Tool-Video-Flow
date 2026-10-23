"""ScrapeCreators documented native field layout; live probe provenance stays explicit."""
import re
from urllib.parse import urlsplit
from db.repository import Repository
from schemas.trends import Metrics, TrendItem
from providers.trends.base import BaseProvider, count, short_text

BASE = "https://api.scrapecreators.com"


def adapt(payload):
    """Only caption/engagement/page URL; discard author/media/transcript objects."""
    if not isinstance(payload, dict):
        return []
    rows = payload.get("aweme_list") or payload.get("search_item_list") or payload.get("item_list") or []
    if not isinstance(rows, list):
        return []
    items = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        video = row.get("aweme_info") if isinstance(row.get("aweme_info"), dict) else row
        identity = str(video.get("aweme_id") or video.get("id") or "")
        title = short_text(video.get("desc"), 240)
        url = str(video.get("url") or video.get("share_url") or "").split("?")[0]
        try:
            parsed = urlsplit(url)
        except ValueError:
            continue
        if not title or not identity or parsed.scheme != "https" or parsed.hostname not in {"www.tiktok.com", "tiktok.com"}:
            continue
        if not re.search(r"/(video|photo)/\d+$", parsed.path):
            continue
        stats = video.get("statistics") if isinstance(video.get("statistics"), dict) else {}
        metrics = Metrics(views=count(stats.get("play_count")), likes=count(stats.get("digg_count")),
                          shares=count(stats.get("share_count")), comments=count(stats.get("comment_count")))
        items.append(TrendItem(id=identity, title=title, summary=short_text(video.get("desc")), url=url,
            platform="tiktok", language=str(video.get("desc_language") or "und"), region=str(video.get("region") or ""),
            metrics=metrics, score_raw=metrics.views + 10*metrics.likes + 20*metrics.shares,
            hashtags=list(dict.fromkeys(re.findall(r"#([\w]+)", title)))[:30]))
    return list({item.id: item for item in items}.values())


class ScrapeCreatorsTikTok(BaseProvider):
    name = "scrapecreators_tiktok"

    def _call(self, endpoint, params):
        def load():
            key = self.settings.scrapecreators_api_key.get_secret_value().strip()
            if not key:
                raise ValueError("Thiếu SCRAPECREATORS_API_KEY; bỏ qua nguồn có phí.")
            repo = self.repository or Repository.for_settings(self.settings)
            token = repo.reserve_trend_call("scrapecreators", self.config.TREND_DAILY_CREDIT_LIMIT, endpoint)
            if token is None:
                raise ValueError("Đã hết ngân sách ScrapeCreators/ngày; chỉ dùng cache và nguồn miễn phí.")
            # Exactly one HTTP attempt. Timeout/401/429 never triggers paid retries.
            raw = self.request(BASE + endpoint, params=params, headers={"x-api-key": key})
            if isinstance(raw, dict):
                repo.finish_trend_call(token, raw.get("credits_charged"))
            if not isinstance(raw, dict) or raw.get("success") is False:
                raise ValueError("ScrapeCreators không trả metadata thành công; xem dashboard credit/quyền API.")
            return adapt(raw)
        try:
            return self.cached([endpoint, params], load)
        except Exception as error:
            self.warn(str(error), error)
            return []

    def _fetch(self, category, limit):
        keywords = self.category_options(category).get("keywords") or category.keywords_vi
        rows = self._call("/v1/tiktok/get-trending-feed", {"region": self.region, "trim": "true"})
        rows = [r for r in rows if self.relevant(r.title, category)]
        if keywords:
            rows += self._call("/v1/tiktok/search/keyword", {"query": keywords[0], "region": self.region,
                              "date_posted": "this-week", "sort_by": "most-liked", "trim": "true"})
        return sorted({r.id: r for r in rows}.values(), key=lambda r: r.score_raw, reverse=True)[:limit]
