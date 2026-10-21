"""Durable, cross-process topic history; suggestions alone do not blacklist."""
from datetime import datetime,timedelta,timezone
from difflib import SequenceMatcher
from pathlib import Path
import re
import unicodedata
from utils.atomic_io import read_json_atomic,write_json_atomic
from utils.file_lock import file_lock


def normalized(text):
    text=unicodedata.normalize("NFKD",text.casefold()).replace("đ","d")
    return " ".join(re.findall(r"[a-z0-9]+","".join(c for c in text if not unicodedata.combining(c))))


def similarity(a,b):
    a,b=normalized(a),normalized(b)
    if not a or not b: return 0.
    na,nb=set(re.findall(r"\d+",a)),set(re.findall(r"\d+",b))
    if na and nb and na.isdisjoint(nb): return 0.
    aa,bb=set(a.split()),set(b.split())
    return max(SequenceMatcher(None,a,b).ratio(),len(aa&bb)/max(1,len(aa|bb)))


def history_rows(output_dir):
    path=Path(output_dir)/"topics_history.json"
    if not path.exists(): return []
    with file_lock(path.with_suffix(".lock")):
        data=read_json_atomic(path)
        rows=data.get("topics",[])
        if not isinstance(rows,list): raise ValueError("topics_history.json: topics phải là danh sách.")
        return rows


def already_made(topic,rows,now=None,source_urls=None):
    now=now or datetime.now(timezone.utc)
    for row in rows:
        if not row.get("project"): continue
        try:
            when=datetime.fromisoformat(row["date"].replace("Z","+00:00"))
            if when.tzinfo is None: when=when.replace(tzinfo=timezone.utc)
        except (ValueError,KeyError,TypeError): continue
        if now-timedelta(days=14)<=when<=now:
            same_source=bool(set(map(str,source_urls or []))&set(row.get("source_urls",[])))
            if same_source or any(similarity(topic,t)>=.78 for t in [row.get("topic",""),row.get("original_topic","")]):
                return row
    return None


def record_topic(output_dir,topic,category,project,*,original_topic=None,source_urls=None):
    path=Path(output_dir)/"topics_history.json"
    with file_lock(path.with_suffix(".lock")):
        data=read_json_atomic(path) if path.exists() else {"topics":[]}
        rows=data["topics"]
        row={"topic":topic,"original_topic":original_topic or topic,"category":category,
            "date":datetime.now(timezone.utc).isoformat(),"project":str(Path(project).resolve()),"source_urls":source_urls or []}
        existing=next((r for r in rows if r.get("project")==row["project"]),None)
        if existing: existing.update({k:v for k,v in row.items() if k!="date"})
        else: rows.append(row)
        write_json_atomic(path,{"topics":rows})
