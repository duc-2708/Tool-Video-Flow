"""Official Firebase API; title/score/comment count only, no article scrape."""
from schemas.trends import Metrics, TrendItem
from providers.trends.base import BaseProvider, count, short_text


class HackerNews(BaseProvider):
    name = "hackernews"

    def _fetch(self, category, limit):
        if category.category_id not in {"cong-nghe", "kinh-doanh", "game"}:
            return []
        def load():
            ids = self.request("https://hacker-news.firebaseio.com/v0/topstories.json")
            result = []
            for identity in (ids if isinstance(ids, list) else [])[:min(limit*2, 20)]:
                if not str(identity).isdigit():
                    continue
                try:
                    row = self.request(f"https://hacker-news.firebaseio.com/v0/item/{identity}.json")
                    if not isinstance(row, dict) or row.get("deleted") or row.get("dead") or not row.get("title"):
                        continue
                    title = short_text(row["title"], 240)
                    if category.category_id != "cong-nghe" and not self.relevant(title, category):
                        continue
                    result.append(TrendItem(id=str(identity), title=title, platform="hackernews", language="en",
                        url=f"https://news.ycombinator.com/item?id={identity}", score_raw=count(row.get("score"))+count(row.get("descendants")),
                        metrics=Metrics(likes=count(row.get("score")), comments=count(row.get("descendants")))))
                except Exception as error:
                    self.warn(f"item {identity}: {error}", error)
            return result
        return self.cached([category.category_id, limit], load)
