"""Public subreddit metadata; a 403/429 is skipped, never worked around."""
import re
from schemas.trends import Metrics, TrendItem
from providers.trends.base import BaseProvider, count, short_text


class Reddit(BaseProvider):
    name = "reddit"

    def _fetch(self, category, limit):
        output = []
        for subreddit in self.category_options(category).get("subreddits", [])[:2]:
            if not re.fullmatch(r"[A-Za-z0-9_]{1,40}", subreddit):
                continue
            def load():
                raw = self.request(f"https://www.reddit.com/r/{subreddit}/hot.json", {"limit": limit, "raw_json": 1})
                result = []
                for child in (raw.get("data") or {}).get("children") or []:
                    row = child.get("data") or {}
                    path = str(row.get("permalink") or "")
                    title = short_text(row.get("title"), 240)
                    if not path.startswith("/r/") or "/comments/" not in path or not title or row.get("over_18") or row.get("stickied"):
                        continue
                    result.append(TrendItem(id=str(row.get("id") or path), title=title, platform="reddit", language="en",
                        url="https://www.reddit.com"+path, metrics=Metrics(likes=count(row.get("score")), comments=count(row.get("num_comments"))),
                        score_raw=count(row.get("score"))+2*count(row.get("num_comments"))))
                return result
            try:
                output += self.cached([subreddit, limit], load)
            except Exception as error:
                self.warn(f"r/{subreddit}: {error}", error)
        return sorted(output, key=lambda r: r.score_raw, reverse=True)[:limit]
