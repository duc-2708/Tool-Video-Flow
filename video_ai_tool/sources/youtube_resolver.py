"""Resolve YouTube identities using only the official Data API. Never fetch pages."""
import re
from urllib.parse import urlsplit, parse_qs, unquote
from sources.youtube_trends import YouTubeTrends
from utils.atomic_io import read_json_atomic
from utils.cache import JsonCache

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
YOUTUBE_HOSTS = {"youtube.com","www.youtube.com","m.youtube.com","youtu.be","www.youtu.be","music.youtube.com"}


class YouTubeCatalog(YouTubeTrends):
    def __init__(self, settings):
        super().__init__(settings, JsonCache(settings.cache_dir,settings.cache_ttl_sec))

    def request(self, endpoint, params, *, cached=False, keyword=False):
        inputs={"endpoint":endpoint,"params":params}
        if cached:
            found=self.cache.get("youtube-style-catalog-v1",inputs)
            if isinstance(found,dict):
                return found
        self.daily_search_limit=self.settings.youtube_max_searches_per_run if keyword else 100
        try:
            raw=self._request(endpoint,params)
        finally:
            self.daily_search_limit=100
        if cached:
            self.cache.set("youtube-style-catalog-v1",inputs,raw)
        return raw

    def quota(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        today=datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
        path=self.settings.cache_dir/"youtube_quota.json"
        state=read_json_atomic(path) if path.exists() else {}
        if state.get("day")==today and any(type(state.get(k)) is not int or state[k]<0 for k in ("estimated_units","search_calls")):
            raise ValueError("File quota local không hợp lệ; chưa gọi YouTube. Kiểm tra ledger trước khi quét.")
        return state if state.get("day")==today else {"day":today,"estimated_units":0,"search_calls":0}


def canonical_video_url(video_id):
    if not VIDEO_ID.fullmatch(video_id):
        raise ValueError("Video ID YouTube không hợp lệ.")
    return "https://www.youtube.com/watch?v="+video_id


def channel_result(item):
    channel_id=item.get("id",{})
    if isinstance(channel_id,dict):
        channel_id=channel_id.get("channelId","")
    if not CHANNEL_ID.fullmatch(channel_id):
        raise ValueError("API trả channel_id không hợp lệ.")
    snippet=item.get("snippet",{})
    return {"kind":"channel","value":channel_id,"label":snippet.get("title") or channel_id,
        "source_url":"https://www.youtube.com/channel/"+channel_id,
        "thumbnail_url":snippet.get("thumbnails",{}).get("default",{}).get("url","")}


def resolve_source(value, api, *, kind="channel"):
    """Return choices. Plain channel names ALWAYS require explicit selection."""
    value=value.strip()
    if not value or len(value)>500:
        raise ValueError("Nhập link YouTube hoặc tên kênh/từ khóa ngắn.")
    looks_url="://" in value or value.startswith(("www.","youtube.com/","youtu.be/","m.youtube.com/"))
    if kind=="keyword":
        if looks_url:
            raise ValueError("Nguồn từ khóa cần văn bản; chọn Kênh để phân giải link YouTube.")
        return {"choices":[{"kind":"keyword","value":value,"label":value,"source_url":"","thumbnail_url":""}],"requires_selection":False}
    channel_id=None;handle=None;video_id=None;playlist_id=None;username=None
    if CHANNEL_ID.fullmatch(value):
        channel_id=value
    elif value.startswith("@"):
        handle=value[1:]
    elif looks_url:
        parsed=urlsplit(value if "://" in value else "https://"+value)
        if parsed.scheme!="https" or parsed.hostname not in YOUTUBE_HOSTS or parsed.username or parsed.password or parsed.port not in (None,443):
            raise ValueError("Chỉ hỗ trợ link HTTPS YouTube chính thức; không scrape nền tảng khác.")
        parts=[unquote(p) for p in parsed.path.split("/") if p]
        query=parse_qs(parsed.query)
        if parsed.hostname in {"youtu.be","www.youtu.be"}:
            video_id=parts[0] if parts else ""
        elif parts and parts[0]=="watch":
            video_id=query.get("v",[""])[0]
        elif len(parts)>=2 and parts[0] in {"shorts","live","embed"}:
            video_id=parts[1]
        elif parts and parts[0].startswith("@"):
            handle=parts[0][1:]
        elif len(parts)>=2 and parts[0]=="channel":
            channel_id=parts[1]
        elif len(parts)>=2 and parts[0]=="user":
            username=parts[1]
        elif parts==["playlist"]:
            playlist_id=query.get("list",[""])[0]
        else:
            raise ValueError("Link YouTube chưa hỗ trợ; dùng @handle hoặc /channel/UC... (link /c/ cần nhập tên kênh để chọn).")
    else:
        raw=api.request("search",{"part":"snippet","q":value,"type":"channel","maxResults":5},cached=True)
        choices=[channel_result(i) for i in raw.get("items",[])]
        return {"choices":choices,"requires_selection":True}
    if video_id is not None:
        canonical_video_url(video_id)
        items=api.request("videos",{"part":"snippet","id":video_id},cached=True).get("items",[])
        if not items:
            raise ValueError("Video không tồn tại hoặc không công khai.")
        snippet=items[0]["snippet"]
        # videos.list alone provides channel ID and name (one quota unit).
        item={"id":snippet["channelId"],"snippet":{"title":snippet.get("channelTitle",snippet["channelId"])}}
    elif playlist_id is not None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{10,100}",playlist_id):
            raise ValueError("Playlist ID không hợp lệ.")
        items=api.request("playlists",{"part":"snippet","id":playlist_id},cached=True).get("items",[])
        if not items:
            raise ValueError("Playlist không tồn tại hoặc không công khai.")
        snippet=items[0]["snippet"]
        item={"id":snippet["channelId"],"snippet":{"title":snippet.get("channelTitle",snippet["channelId"])}}
    else:
        params={"part":"snippet"}
        if channel_id:
            if not CHANNEL_ID.fullmatch(channel_id):
                raise ValueError("Channel ID không hợp lệ.")
            params["id"]=channel_id
        elif handle:
            if not re.fullmatch(r"[\w.\-·]{3,100}",handle):
                raise ValueError("YouTube handle không hợp lệ.")
            params["forHandle"]=handle
        elif username:
            params["forUsername"]=username
        else:
            raise ValueError("Thiếu định danh kênh YouTube.")
        items=api.request("channels",params,cached=True).get("items",[])
        if not items:
            raise ValueError("Không tìm thấy kênh công khai.")
        item=items[0]
    result={"choices":[channel_result(item)],"requires_selection":False}
    if playlist_id:
        result["notice"]="Link playlist được quy về kênh sở hữu; khi quét sẽ đọc uploads của kênh đó."
    return result
