"""Shared publisher names and complete web-source credits (no guessed dates)."""
from urllib.parse import urlsplit
from pipeline.projects import read_json


def publisher_name(url):
    host = (urlsplit(str(url)).hostname or "web").removeprefix("www.").lower()
    names = {"reuters.com":"Reuters", "apnews.com":"AP", "bbc.com":"BBC", "bbc.co.uk":"BBC", "cnn.com":"CNN", "nhk.or.jp":"NHK", "yonhapnews.co.kr":"Yonhap"}
    return next((name for domain,name in names.items() if host == domain or host.endswith("."+domain)),host)


def source_credit_lines(project):
    discovery_lines=[]
    path=project/"topic_discovery.json"
    if path.exists():
        try:
            suggestion=read_json(path).get("suggestion",{})
            discovery_lines=["", "NGUỒN KHÁM PHÁ CHỦ ĐỀ — metadata, không thay cho kiểm chứng fact"]
            discovery_lines.extend(f"- {publisher_name(url)} | {url}" for url in suggestion.get("source_urls",[]))
        except (OSError,ValueError): pass
    brief_path = project/"brief.json"
    if not brief_path.exists():
        return discovery_lines
    try:
        brief = read_json(brief_path)
    except (OSError,ValueError):
        return discovery_lines
    rows = list(brief.get("facts",[]))
    sources = project/"sources.json"
    if sources.exists():
        try:
            rows += [row for row in read_json(sources).get("sources",[]) if row.get("platform") == "web"]
        except (OSError,ValueError):
            pass
    merged = {}
    for row in rows:
        url = row.get("source_url") or row.get("url")
        if not url:
            continue
        previous = merged.setdefault(url,{})
        for key,value in row.items():
            if value is not None and not previous.get(key):
                previous[key] = value
    result = ["", "NGUỒN NGHIÊN CỨU — ngôn ngữ gốc; ngày xuất bản"]
    for url,row in merged.items():
        result.append(f"- {row.get('source_name') or publisher_name(url)} | {url} | {row.get('published_at') or 'Không rõ ngày'} | ngôn ngữ gốc: {row.get('source_lang','vi')}")
    return result+discovery_lines
