"""Preview official YouTube metadata, then explicitly approve URL style analysis."""
import argparse
import hashlib
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re
import sys
from config.categories import resolve_category
from config.settings import get_settings
from db.repository import Repository, utcnow
from pipeline.style_learner import VideoStyleProvider, analysis_prompt, style_diagnostics, storage
from schemas.style import AnalysisRecord, StyleAnalysis
from sources.youtube_resolver import YouTubeCatalog, resolve_source, canonical_video_url, VIDEO_ID
from utils.atomic_io import read_json_atomic, write_json_atomic
from utils.cache import cache_key
from utils.console import configure_console
from utils.file_lock import file_lock


def analysis_path(settings, category_id, video_id):
    category_id=resolve_category(settings,category_id).category_id
    canonical_video_url(video_id)
    folder=storage(settings)/category_id
    path=folder/(video_id+".json")
    if folder.is_symlink() or path.is_symlink() or not path.resolve().is_relative_to(storage(settings)):
        raise ValueError("Đường dẫn phân tích YouTube không hợp lệ.")
    return path


def add_source(settings, category, resolved):
    category=resolve_category(settings,category).category_id
    if resolved.get("kind")=="channel":
        from sources.youtube_resolver import CHANNEL_ID
        if not CHANNEL_ID.fullmatch(resolved.get("value","")):
            raise ValueError("Channel ID không hợp lệ.")
    elif resolved.get("kind")!="keyword" or not resolved.get("value","").strip():
        raise ValueError("Nguồn cần là kênh hoặc từ khóa.")
    return Repository.for_settings(settings).add_source(category,**resolved)


def duration_seconds(value):
    match=re.fullmatch(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?",value or "")
    if not match:
        return 0.
    d,h,m,s=[float(v or 0) for v in match.groups()]
    return d*86400+h*3600+m*60+s


def candidate(item, video_id, source_id, *, now, settings, mode):
    snippet=item.get("snippet",{})
    status=item.get("status",{})
    seconds=duration_seconds(item.get("contentDetails",{}).get("duration"))
    published=snippet.get("publishedAt","")
    reason=""
    try:
        when=datetime.fromisoformat(published.replace("Z","+00:00"))
        if when.tzinfo is None:
            raise ValueError
    except (ValueError,AttributeError):
        when=None
        reason="Không có ngày đăng hợp lệ."
    if not item or status.get("privacyStatus")!="public" or status.get("uploadStatus") not in (None,"processed"):
        reason="Video không công khai, đã bị xóa hoặc không phát được."
    elif status.get("embeddable") is False:
        reason="Video không cho phép phát nhúng; bỏ qua phân tích URL."
    elif snippet.get("liveBroadcastContent") in {"live","upcoming"} or not seconds:
        reason="Đang live/sắp phát hoặc không đọc được thời lượng."
    elif seconds>settings.scan_max_video_sec:
        reason=f"Quá dài: {seconds:g}s > SCAN_MAX_VIDEO_SEC={settings.scan_max_video_sec:g}s."
    elif when and when<now-timedelta(days=settings.scan_max_age_days):
        reason=f"Quá cũ: vượt {settings.scan_max_age_days} ngày."
    elif when and when>now+timedelta(minutes=5):
        reason="Video chưa được xuất bản."
    # Public Data API exposes no reliable isShort flag. Do not scrape to infer it.
    short_hint=seconds<=180
    if not reason and ((mode=="shorts" and not short_hint) or (mode=="regular" and short_hint)):
        reason="Không thuộc nhóm thời lượng đã chọn (Shorts chỉ được ước lượng theo ngưỡng 180s)."
    return {"platform":"youtube","video_id":video_id,"url":canonical_video_url(video_id),
        "title":snippet.get("title") or video_id,"channel_id":snippet.get("channelId", ""),
        "published_at":published or None,"duration_sec":seconds,"views":int(item.get("statistics",{}).get("viewCount",0) or 0),
        "source_ids":[source_id],"decision":"skipped" if reason else "ready","reason":reason,"shorts_estimated":short_hint}


def preview_scan(settings, category, *, source_id=None, maximum=None, mode="all", order="date", api=None, progress=lambda message:None, now=None):
    """Metadata only. No Gemini instance or media network requests here."""
    category=resolve_category(settings,category).category_id
    if mode not in {"all","shorts","regular"} or order not in {"date","viewCount"}:
        raise ValueError("Kiểu video hoặc thứ tự quét không hợp lệ.")
    limit=batch_limit(settings,maximum)
    repository=Repository.for_settings(settings)
    sources=repository.sources(category,active_only=True)
    if source_id is not None:
        sources=[s for s in sources if s["id"]==source_id]
    if not sources:
        raise ValueError("Chưa có nguồn đang bật trong danh mục. Hãy thêm hoặc bật nguồn trước.")
    api=api or YouTubeCatalog(settings)
    now=now or datetime.now(timezone.utc)
    rows={};warnings=[];diagnostics=style_diagnostics(settings)
    for source in sources:
        progress("Đang đọc nguồn: "+source["label"])
        try:
            playlist=None
            if source["kind"]=="channel":
                items=api.request("channels",{"part":"contentDetails","id":source["value"]}).get("items",[])
                if not items:
                    raise ValueError("Kênh không tồn tại hoặc không truy cập được.")
                playlist=items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
            page=None;seen_pages=set();ready=0;stop=False
            # Bounded traversal also protects all-private/all-too-long channels.
            for _ in range(20):
                params={"part":"snippet,contentDetails" if playlist else "snippet","maxResults":50}
                if playlist:
                    params["playlistId"]=playlist
                else:
                    params.update(q=source["value"],type="video",order=order,
                        publishedAfter=(now-timedelta(days=settings.scan_max_age_days)).isoformat(),safeSearch="moderate")
                if page:
                    params["pageToken"]=page
                raw=api.request("playlistItems" if playlist else "search",params,keyword=not bool(playlist))
                ids=[]
                for entry in raw.get("items",[]):
                    vid=(entry.get("contentDetails",{}).get("videoId") or entry.get("snippet",{}).get("resourceId",{}).get("videoId")) if playlist else entry.get("id",{}).get("videoId")
                    if not isinstance(vid,str) or not VIDEO_ID.fullmatch(vid) or vid in ids:
                        continue
                    existing=repository.video(category,"youtube",vid)
                    if existing:
                        repository.save_video(category,"youtube",vid,status=existing["status"],source_ids=[source["id"]])
                        row={**existing,"source_ids":[source["id"]],"decision":"done" if existing["status"]=="done" else "skipped",
                            "reason":"Đã học." if existing["status"]=="done" else existing.get("error") or "Đã ghi nhận; chọn Thử lại/Học lại nếu cần."}
                        rows.setdefault(vid,row)
                        # Uploads are newest first; stop at the first known boundary.
                        if playlist:
                            stop=True
                            break
                        continue
                    ids.append(vid)
                details={}
                if ids:
                    details={item["id"]:item for item in api.request("videos",{"part":"snippet,contentDetails,statistics,status","id":",".join(ids)}).get("items",[])}
                for vid in ids:
                    row=candidate(details.get(vid,{}),vid,source["id"],now=now,settings=settings,mode=mode)
                    if vid in rows:
                        rows[vid]["source_ids"]=list(dict.fromkeys(rows[vid]["source_ids"]+[source["id"]]))
                        continue
                    if row["decision"]=="ready":
                        if ready>=limit:
                            # Do not persist deferred entries; they remain available next run.
                            row.update(decision="deferred",reason="Ngoài giới hạn lô này; để lần quét sau.")
                        else:
                            ready+=1
                    elif row["decision"]=="skipped":
                        repository.save_video(category,"youtube",vid,status="skipped",source_ids=[source["id"]],
                            **video_fields(row),error=row["reason"])
                    rows[vid]=row
                page=raw.get("nextPageToken")
                if stop or ready>=limit or not page or page in seen_pages:
                    break
                seen_pages.add(page)
            repository.scanned(source["id"])
        except Exception as error:
            diagnostics.record_exception(error,"Quét nguồn "+str(source["id"]))
            warnings.append(source["label"]+": "+diagnostics.redact(str(error)))
    values=sorted(rows.values(),key=lambda r:r.get("published_at") or "",reverse=True)
    selected=0
    for row in values:
        if row["decision"]=="ready":
            selected+=1
            if selected>limit:
                row.update(decision="deferred",reason="Ngoài giới hạn toàn bộ lô; để lần quét sau.")
    return {"category_id":category,"videos":values,"warnings":warnings,"created_at":utcnow()}


def video_fields(row):
    return {key:row.get(key) for key in ("url","title","channel_id","published_at","duration_sec")}


def estimate_selection(settings, rows, category=None):
    rows=[r for r in rows if r.get("decision")=="ready"]
    prompt=analysis_prompt(settings)
    from pipeline.style_raw import raw_path
    from utils.style_rate_limit import estimated_video_tokens
    paid=[]
    for row in rows:
        if not category:
            paid.append(row);continue
        from pipeline.style_raw import RawResponse,StyleRawError
        store=RawResponse(raw_path(settings,category,hashlib.sha256(row["url"].encode("utf-8")).hexdigest()),{},style_diagnostics(settings))
        if store.path.exists():
            try: store.parse()
            except StyleRawError: pass
        if not store.path.exists():
            paid.append(row)
    total=sum(r["duration_sec"] for r in rows)
    return {"videos":len(rows),"duration_sec":total,
        "estimated_input_tokens":sum(estimated_video_tokens(settings,min(r["duration_sec"],settings.style_max_video_sec),len(prompt)) for r in paid),"estimated_output_tokens":settings.style_max_output_tokens*len(paid)}


def batch_limit(settings, maximum=None):
    cap=min(settings.scan_max_new_videos,settings.style_max_videos_per_run)
    if maximum is None:
        return cap
    if type(maximum) is not int or not 1<=maximum<=cap:
        raise ValueError(f"Số video phải từ 1 đến {cap}, theo SCAN_MAX_NEW_VIDEOS/STYLE_MAX_VIDEOS_PER_RUN.")
    return maximum


def retry_candidates(settings, category, *, video_id=None, platform="youtube", relearn=False, source_id=None):
    """Prepare a new explicit approval; do not erase a working analysis first."""
    category=resolve_category(settings,category).category_id
    rows=Repository.for_settings(settings).videos(category,source_id)
    result=[]
    for row in rows:
        if row["platform"]!=platform or (video_id is not None and row["video_id"]!=video_id):
            continue
        if row["permanent_skip"]:
            continue
        if not relearn and row["status"]!="failed":
            continue
        result.append({**row,"decision":"ready","reason":"Học lại có xác nhận" if relearn else "Thử lại video lỗi",
            "force":relearn,"source_ids":[]})
    return result


def learn_selected(settings, category, rows, *, confirmed=False, provider=None, progress=lambda message:None):
    if not confirmed:
        raise ValueError("Cần xác nhận chi phí trước khi gọi Gemini.")
    category=resolve_category(settings,category).category_id
    rows=list({(r.get("platform","youtube"),r["video_id"]):r for r in rows if r.get("decision")=="ready"}.values())
    if len(rows)>min(settings.scan_max_new_videos,settings.style_max_videos_per_run):
        raise ValueError("Vượt giới hạn số video học mỗi lần.")
    repo=Repository.for_settings(settings);diagnostics=style_diagnostics(settings)
    results=[];changed=False;owned=provider is None;warnings=[]
    prompt=analysis_prompt(settings)
    try:
        for row in rows:
            vid=row["video_id"];platform=row.get("platform","youtube")
            progress("Đang học: "+row["title"])
            try:
                with file_lock(storage(settings)/(cache_key([category,platform,vid])+".learn.lock"),timeout=1):
                    old=repo.video(category,platform,vid)
                    if old and (old["permanent_skip"] or old["status"]=="done" and not row.get("force")):
                        results.append({"filename":row["title"],"status":"cached","error":None})
                        continue
                    if platform=="local":
                        from pipeline.style_learner import analyze_one
                        result=analyze_one(settings,row["url"],provider=provider,progress=progress,force=bool(row.get("force")))
                        results.append(result);changed=True
                        continue
                    if platform!="youtube":
                        raise ValueError("Chỉ hỗ trợ YouTube và video mẫu local.")
                    url=canonical_video_url(vid)
                    if not 0<float(row["duration_sec"])<=settings.scan_max_video_sec:
                        raise ValueError("Video vượt giới hạn thời lượng; quét lại metadata trước khi học.")
                    from pipeline.style_raw import RawResponse,raw_path,reuse_raw
                    from utils.style_rate_limit import estimated_video_tokens
                    raw_identity={"file_hash":"youtube:"+vid,"notes_hash":cache_key(""),"model":settings.require_style_model(),"prompt_hash":cache_key(prompt),"version":2}
                    store=RawResponse(raw_path(settings,category,hashlib.sha256(url.encode("utf-8")).hexdigest()),raw_identity,diagnostics,
                        duration_limit=min(row["duration_sec"],settings.style_max_video_sec))
                    analysis=reuse_raw(store,force=bool(row.get("force")))
                    if analysis is not None:
                        progress("Đã parse lại bản thô YouTube, không gọi Gemini.")
                    else:
                        if provider is None:
                            provider=VideoStyleProvider(settings)
                        provider.raw_store=store;provider.use_existing_raw=False
                        provider.video_info={"duration_sec":row["duration_sec"],"size_bytes":None}
                        duration=min(row["duration_sec"],settings.style_max_video_sec)
                        provider.request_tokens=estimated_video_tokens(settings,duration,len(prompt))
                        value=provider.analyze_url(url,prompt+
                            f"\nThời lượng đoạn phân tích 0–{duration:g}s: {duration:g}s; video gốc {row['duration_sec']:g}s. Chỉ học phong cách, không sao chép nội dung.",progress)
                        if store.revision==0:
                            store.save(value if isinstance(value,str) else value.model_dump_json() if isinstance(value,StyleAnalysis) else json.dumps(value,ensure_ascii=False))
                        analysis=store.parse()
                    if not analysis.scenes:
                        raise ValueError("Gemini thiếu scenes[] chi tiết.")
                    expected=min(row["duration_sec"],settings.style_max_video_sec)
                    if abs(analysis.duration_sec-expected)>max(2,expected*.05) and not (analysis.duration_sec<=row["duration_sec"]+2 and store.revision==0):
                        raise ValueError("Thời lượng phân tích không khớp metadata YouTube.")
                    scope=[f"Chỉ phân tích 0–{expected:g}s của video {row['duration_sec']:g}s."] if expected<row["duration_sec"] else []
                    record=AnalysisRecord(version=2,filename=url,file_hash="youtube:"+vid,notes_hash=cache_key(""),
                        model=settings.require_style_model(),prompt_hash=cache_key(prompt),category_id=category,category_confirmed=True,analysis=analysis,warnings=scope+analysis.normalization_notes)
                    path=analysis_path(settings,category,vid)
                    if path.exists():
                        current=AnalysisRecord.model_validate(read_json_atomic(path))
                        if current.file_hash!=record.file_hash:
                            raise ValueError("Tên file phân tích trùng mẫu khác; đổi tên mẫu local trước khi học URL này.")
                    write_json_atomic(path,record.model_dump(mode="json"))
                    saved=AnalysisRecord.model_validate(read_json_atomic(path))
                    if cache_key(saved.model_dump(mode="json"))!=cache_key(record.model_dump(mode="json")):
                        raise OSError("Không xác nhận được file phân tích đã ghi; chưa đánh dấu done.")
                    repo.save_video(category,"youtube",vid,status="done",source_ids=row.get("source_ids",[]),force=True,
                        **{**video_fields(row),"url":url},analysis_path=path.relative_to(settings.root_dir).as_posix(),
                        analyzed_at=utcnow(),error=None,permanent_skip=0)
                    changed=True
                    results.append({"filename":row["title"],"status":"done","error":None})
            except Exception as error:
                diagnostics.record_exception(error,"Học video "+vid)
                message=diagnostics.redact(str(error))
                # On failed re-learning preserve the previous good profile/analysis.
                previous=repo.video(category,platform,vid)
                if not previous or previous["status"]!="done":
                    repo.save_video(category,platform,vid,status="failed",source_ids=row.get("source_ids",[]),**video_fields(row),error=message)
                results.append({"filename":row["title"],"status":"failed","error":message})
    finally:
        if owned and provider is not None:
            try:
                provider.close()
            except Exception as error:
                diagnostics.record_exception(error,"Đóng client Gemini Style")
                warnings.append("Không đóng được client Gemini; kết quả từng video đã được lưu.")
    if changed:
        try:
            from pipeline.category_style import rebuild_category
            for kind in (None,"news","review","story"):
                rebuild_category(settings,category,video_type=kind)
        except Exception as error:
            diagnostics.record_exception(error,"Tổng hợp hồ sơ sau học")
            warnings.append("Đã lưu phân tích nhưng chưa tổng hợp được hồ sơ: "+diagnostics.redact(str(error)))
    return {"results":results,"warnings":warnings}


def main(argv=None):
    configure_console()
    parser=argparse.ArgumentParser(description="Quét metadata YouTube chính thức, xác nhận rồi học phong cách bằng URL")
    parser.add_argument("--category",required=True)
    parser.add_argument("--add")
    parser.add_argument("--kind",choices=["channel","keyword"],default="channel")
    parser.add_argument("--choose",help="Channel ID được chọn trong kết quả tìm tên kênh")
    parser.add_argument("--scan",action="store_true")
    parser.add_argument("--source",type=int)
    parser.add_argument("--max",type=int,dest="maximum")
    parser.add_argument("--mode",choices=["all","shorts","regular"],default="all")
    parser.add_argument("--order",choices=["date","viewCount"],default="date")
    parser.add_argument("--yes",action="store_true")
    parser.add_argument("--retry-failed",action="store_true")
    args=parser.parse_args(argv);settings=None
    try:
        settings=get_settings();category=resolve_category(settings,args.category).category_id
        api=YouTubeCatalog(settings)
        if args.add:
            resolved=resolve_source(args.add,api,kind=args.kind)
            choices=resolved["choices"]
            if not choices:
                raise ValueError("Không tìm thấy kênh phù hợp.")
            if resolved["requires_selection"]:
                for row in choices:
                    print(row["value"]+" · "+row["label"])
                choice=args.choose
                if not choice and sys.stdin.isatty():
                    choice=input("Chọn channel_id (không tự chọn): ").strip()
                choices=[r for r in choices if r["value"]==choice]
                if not choices:
                    print("Chạy lại với --choose <channel_id> để xác nhận kênh.")
                    return 2
            saved=add_source(settings,category,choices[0]);print(f"Đã thêm nguồn #{saved['id']}: {saved['label']}")
            if resolved.get("notice"):
                print(resolved["notice"])
        if not args.scan and not args.retry_failed:
            if not args.add:
                parser.error("Chọn --add hoặc --scan/--retry-failed.")
            return 0
        if args.retry_failed:
            videos=retry_candidates(settings,category,source_id=args.source)
            videos=videos[:batch_limit(settings,args.maximum)]
        else:
            preview=preview_scan(settings,category,api=api,source_id=args.source,maximum=args.maximum,mode=args.mode,order=args.order,progress=print)
            for warning in preview["warnings"]:
                print("Cảnh báo: "+warning)
            videos=preview["videos"]
        for row in videos:
            print(f"{row['video_id']} · {row['title']} · {row['duration_sec']:g}s · {row.get('published_at') or '?'} · {row['decision']} · {row['reason']}")
        selected=[r for r in videos if r["decision"]=="ready"]
        estimate=estimate_selection(settings,selected,category)
        print(json.dumps(estimate,ensure_ascii=False))
        print("Chỉ học phong cách, không sao chép nội dung. Ước lượng token, không phải giá tính phí chính xác.")
        if not selected:
            return 0
        approved=args.yes or (sys.stdin.isatty() and input("Xác nhận gọi Gemini có thể tốn phí? [y/N] ").strip().lower()=="y")
        if not approved:
            print("Chưa gọi Gemini. Dùng --yes để xác nhận sau khi xem bảng/ước lượng.")
            return 0
        outcome=learn_selected(settings,category,selected,confirmed=True,progress=print)
        for result in outcome["results"]:
            print(result["filename"]+": "+result["status"]+(" · "+result["error"] if result["error"] else ""))
        for warning in outcome["warnings"]:
            print(warning)
        return int(any(r["status"]=="failed" for r in outcome["results"]))
    except Exception as error:
        if settings is None:
            print("Không nạp được cấu hình; kiểm tra .env theo .env.example, không in key.")
        else:
            diagnostics=style_diagnostics(settings);diagnostics.record_exception(error,"Scan CLI")
            print(diagnostics.redact(str(error)))
        return 1


if __name__=="__main__":
    raise SystemExit(main())
