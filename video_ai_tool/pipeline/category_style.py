"""Local category profile rebuilds reuse Style Learner's analysis and aggregator."""
from collections import Counter
import math
from pathlib import Path
from statistics import mean
from config.categories import resolve_category
from schemas.style import StyleProfile,SceneDurationProfile,ScenePattern,RuleFrequency
from utils.atomic_io import read_json_atomic,write_json_atomic
from utils.cache import cache_key
from utils.file_lock import file_lock


def folder(settings):
    path=settings.root_dir/"config/style_profiles"
    if path.is_symlink() or not path.resolve().is_relative_to(settings.root_dir.resolve()):
        raise ValueError("Thư mục hồ sơ phải nằm trong config/style_profiles/.")
    path.mkdir(parents=True,exist_ok=True)
    return path.resolve()


def profile_file(settings,category=None,video_type=None):
    if video_type not in {None,"news","review","story"}:
        raise ValueError("Loại hồ sơ phải là news/review/story.")
    name=resolve_category(settings,category).category_id if category else "_default"
    path=folder(settings)/(name+("."+video_type if video_type else "")+".json")
    if path.resolve().parent!=folder(settings) or path.is_symlink():
        raise ValueError("Đường dẫn hồ sơ không hợp lệ.")
    return path


def token(category_id,video_type=None):
    return "@category:"+category_id+(":"+video_type if video_type else "")


def default_profile(settings):
    path=profile_file(settings)
    if path.is_file():
        return StyleProfile.model_validate(read_json_atomic(path))
    from schemas.style import PaceRange,CaptionStyle,AudioStyle
    profile=StyleProfile(name="Phong cách mặc định chung",slug="@default",reference_hashes=[],reference_files=[],reference_texts=[],
        hook_templates=["Điều gì khiến {topic} đáng chú ý?"],hook_techniques=["Câu hỏi có căn cứ"],
        structure=[{"name":"hook","fraction":.1},{"name":"bối cảnh","fraction":.2},{"name":"giải thích","fraction":.5},{"name":"kết","fraction":.2}],
        shot_seconds=PaceRange(mean=3,minimum=1.5,maximum=4),speech_words_per_sec=PaceRange(mean=2.6,minimum=2.4,maximum=2.8),
        narration_rules=["Viết tự nhiên, mỗi cảnh một ý, chỉ dựa trên fact."],broll_patterns=["stock b-roll"],visual_effects=["zoom_in","pan_left"],transitions=["cut","fade"],
        captions=CaptionStyle(),audio=AudioStyle(),ending_techniques=["Câu hỏi hoặc nhận định có căn cứ"],reusable_rules=["Chỉ dùng fact trong brief.","Không lặp ý để kéo dài."],rule_frequencies=[],
        video_count=0,confidence_label="mặc định",narrative_flows=["hook → bối cảnh → giải thích → ý nghĩa → kết"],
        connective_phrases=["Nhưng điều đáng nói về {topic} là..."],shots_per_10_sec=10/3)
    for duration,count in ((30,5),(60,10),(90,14),(120,18),(180,24)):
        times=durations_for_count([.5,1,1,1,.7],count,duration)
        profile.scene_pacing.append(SceneDurationProfile(duration_sec=duration,scene_count=count,min_scene_count=count,max_scene_count=count,
            avg_scene_sec=duration/count,min_scene_sec=min(times),max_scene_sec=max(times),durations_sec=times))
    write_json_atomic(path,profile.model_dump(mode="json"))
    from pipeline.style_safety import sanitize_profile
    return sanitize_profile(profile)


def durations_for_count(weights,count,duration):
    """Resample the observed long/short scene rhythm, preserving requested total."""
    weights=weights or [1.]
    sampled=[weights[min(len(weights)-1,int(i*len(weights)/count))] for i in range(count)]
    base=1.5
    extra=max(0.,duration-base*count)
    total=sum(sampled)
    values=[base+extra*w/total for w in sampled]
    values[-1]=duration-sum(values[:-1])
    return values


def enrich(profile,records):
    from pipeline.style_profile import frequent
    analyses=[r.analysis for r in records]
    profile.warnings=list(dict.fromkeys(profile.warnings+[w for r in records for w in r.warnings]))
    # Prefer the most frequent observed role sequence, retaining temporal order.
    detailed=[a for a in analyses if a.scenes]
    rates=[len(a.scenes)/a.duration_sec for a in detailed]
    chosen=None
    if detailed:
        sequences=Counter(tuple(s.purpose for s in a.scenes) for a in detailed)
        sequence=sequences.most_common(1)[0][0]
        chosen=next(a for a in detailed if tuple(s.purpose for s in a.scenes)==sequence)
    weights=[s.end_sec-s.start_sec for s in chosen.scenes] if chosen else [p.duration_sec for p in analyses[0].structure]
    profile.scene_pacing=[]
    for duration in ((30,60,90,120,180) if detailed else ()):
        maximum=max(2,int(duration/1.5))
        count=min(maximum,max(2,round(mean(rates)*duration)))
        times=durations_for_count(weights,count,duration)
        profile.scene_pacing.append(SceneDurationProfile(duration_sec=duration,scene_count=count,
            min_scene_count=min(maximum,max(2,round(min(rates)*duration))),max_scene_count=min(maximum,max(2,round(max(rates)*duration))),
            avg_scene_sec=duration/count,min_scene_sec=min(times),max_scene_sec=max(times),durations_sec=times))
    flows=frequent([[a.narrative_flow] if a.narrative_flow else [" → ".join(s.name for s in a.structure)] for a in analyses])
    profile.narrative_flows=[v for v,n in flows]
    phrases=frequent([a.connective_phrases+[s.transition_to_next.connective_template for s in a.scenes if s.transition_to_next] for a in analyses])
    # A template never imports the original topic into generated narration.
    phrases=[(v,n) for v,n in phrases if v and ("{topic}" in v or len(v.split())<=12)]
    profile.connective_phrases=[v for v,n in phrases][:12]
    profile.connective_frequencies=[RuleFrequency(rule=v,video_count=n) for v,n in phrases[:12]]
    profile.scene_patterns=[]
    if chosen:
        for index,scene in enumerate(chosen.scenes):
            similar=[a.scenes[min(len(a.scenes)-1,round(index*(len(a.scenes)-1)/max(1,len(chosen.scenes)-1)))] for a in detailed]
            common=lambda rows:[v for v,n in frequent(rows)]
            transitions=common([[s.transition_to_next.type] if s.transition_to_next else [] for s in similar])
            connect=common([[s.transition_to_next.connective_template] if s.transition_to_next else [] for s in similar])
            known_mean=lambda values:mean(known) if (known:=[v for v in values if v is not None]) else None
            profile.scene_patterns.append(ScenePattern(purpose=scene.purpose,fraction=(scene.end_sec-scene.start_sec)/sum(weights),
                shot_count=known_mean(s.shot_count for s in similar),average_shot_sec=known_mean(s.average_shot_sec for s in similar),
                visual_types=common([s.visual_types for s in similar]),effects=common([s.camera_effects for s in similar]),
                overlay_styles=common([[o.position+": "+o.emphasis for o in s.overlays] for s in similar]),
                sfx=common([s.sfx for s in similar]),transition=transitions[0] if transitions else "cut",connective_template=connect[0] if connect else ""))
    profile.reference_texts=list(dict.fromkeys(profile.reference_texts+[s.narration_summary for a in analyses for s in a.scenes]))
    shot_rates=[sum(s.shot_count for s in a.scenes)/a.duration_sec*10 if a.scenes and all(s.shot_count is not None for s in a.scenes) else a.pacing.cuts_per_10_sec for a in analyses]
    profile.shots_per_10_sec=mean(known) if (known:=[v for v in shot_rates if v is not None]) else 0
    profile.video_count=len({r.file_hash for r in records})
    profile.confidence_label="ổn" if profile.video_count>=3 else "yếu" if profile.video_count==1 else "đang tích lũy"
    if len(detailed)<len(analyses):
        profile.warnings.append("Có phân tích cũ chưa có scenes[]; bảng số cảnh chỉ dùng mẫu đã phân tích chi tiết. Phân tích lại mẫu cũ để bổ sung.")
    from pipeline.style_safety import sanitize_profile
    return sanitize_profile(profile)


def snapshot(settings,category):
    from pipeline.style_library import list_videos,resolve_video,read_record
    from pipeline.style_learner import digest_file
    from db.repository import Repository,utcnow
    from schemas.style import AnalysisRecord
    repository=Repository.for_settings(settings)
    records=[];signature=[];warnings=[]
    for name in list_videos(settings,category):
        path=resolve_video(settings,name)
        try:
            file_hash=digest_file(path)
            learned=repository.video(category,"local",file_hash)
            if learned and learned["permanent_skip"]:
                signature.append([name,file_hash,"permanently_skipped"])
                continue
            notes=path.with_suffix(".txt")
            if notes.resolve().parent!=path.parent:
                raise ValueError("Ghi chú nằm ngoài thư viện.")
            notes_hash=cache_key(notes.read_text(encoding="utf-8")[:8000] if notes.is_file() else "")
            try:
                record=read_record(settings,name)
                record_hash=cache_key(record.model_dump(mode="json"))
                if record.file_hash!=file_hash or record.notes_hash!=notes_hash:
                    raise ValueError("video/ghi chú đã đổi, cần phân tích lại")
                records.append(record)
                from pipeline.style_library import record_path
                relative=record_path(settings,name).relative_to(settings.root_dir).as_posix()
                if not learned or learned["status"]!="done" or learned["analysis_path"]!=relative:
                    repository.save_video(category,"local",file_hash,status="done",force=True,title=path.stem,url=name,
                        duration_sec=record.analysis.duration_sec,analyzed_at=utcnow(),analysis_path=relative,error=None)
            except (OSError,ValueError) as error:
                record_hash="pending"
                warnings.append(f"{name}: chưa có phân tích còn hiệu lực ({type(error).__name__}).")
            signature.append([name,file_hash,notes_hash,record_hash])
        except (OSError,ValueError) as error:
            signature.append([name,type(error).__name__])
            warnings.append(f"{name}: không đọc được file ({type(error).__name__}).")
    for learned in repository.videos(category):
        if learned["platform"]!="youtube" or learned["status"]!="done" or learned["permanent_skip"]:
            continue
        try:
            from pipeline.scan_sources import analysis_path
            expected=analysis_path(settings,category,learned["video_id"])
            path=settings.root_dir/(learned["analysis_path"] or "")
            if path.resolve()!=expected.resolve() or path.is_symlink():
                raise ValueError("Đường dẫn YouTube không khớp thư viện.")
            record=AnalysisRecord.model_validate(read_json_atomic(path))
            if record.file_hash!="youtube:"+learned["video_id"] or record.category_id!=category:
                raise ValueError("Phân tích không khớp video/danh mục.")
            records.append(record)
            signature.append(["youtube",learned["video_id"],cache_key(record.model_dump(mode="json"))])
        except (OSError,ValueError) as error:
            signature.append(["youtube",learned["video_id"],"unavailable"])
            warnings.append(f"YouTube {learned['video_id']}: không đọc được phân tích ({type(error).__name__}).")
    return records,signature,warnings


def rebuild_category(settings,category,*,force=False,video_type=None):
    from pipeline.style_profile import aggregate
    category=resolve_category(settings,category)
    records,signature,warnings=snapshot(settings,category.category_id)
    if video_type:
        records=[r for r in records if r.analysis.suggested_type==video_type]
    source_hash=cache_key([signature,video_type,4])
    path=profile_file(settings,category.category_id,video_type)
    with file_lock(path.with_suffix(".lock"),timeout=1):
        old=StyleProfile.model_validate(read_json_atomic(path)) if path.is_file() else None
        if old and old.source_signature==source_hash and not force:
            return old
        unique=list({r.file_hash:r for r in records}.values())
        if unique:
            profile=enrich(aggregate(unique,category.name),unique)
        else:
            profile=default_profile(settings).model_copy(deep=True)
            profile.video_count=0;profile.confidence_label="mặc định"
            profile.reference_hashes=[];profile.reference_files=[];profile.reference_texts=[]
            warnings.append("chưa có video mẫu cho danh mục này")
        profile.category_id=category.category_id;profile.video_type=video_type
        profile.name=category.name+(" · "+video_type if video_type else "")
        profile.slug=token(category.category_id,video_type)
        profile.source_signature=source_hash
        profile.warnings=list(dict.fromkeys(profile.warnings+warnings))
        if old:
            # User rendering preferences survive re-aggregation of observations.
            for name in ("visual_theme","visual_templates","progress_tracker","progress_labels"):
                setattr(profile,name,getattr(old,name))
            profile.captions.appearance=old.captions.appearance
            profile.locked_fields=list(old.locked_fields)
            for name in old.locked_fields:
                setattr(profile,name,list(getattr(old,name)))
            if "connective_phrases" in old.locked_fields:
                from pipeline.style_profile import key
                allowed={key(p) for p in profile.connective_phrases}
                profile.connective_frequencies=[f for f in profile.connective_frequencies if key(f.rule) in allowed]
        from pipeline.style_safety import sanitize_profile
        profile=sanitize_profile(profile)
        write_json_atomic(path,profile.model_dump(mode="json"))
        return profile


def resolve_profile(settings,category,video_type=None,*,rebuild=True):
    """Return profile, selector token and notices; never calls Gemini."""
    category=resolve_category(settings,category)
    primary=rebuild_category(settings,category.category_id) if rebuild else StyleProfile.model_validate(read_json_atomic(profile_file(settings,category.category_id)))
    if video_type:
        typed=rebuild_category(settings,category.category_id,video_type=video_type)
        if typed.video_count:
            return typed,token(category.category_id,video_type),list(typed.warnings)
    if primary.video_count:
        return primary,token(category.category_id),list(primary.warnings)
    default=default_profile(settings).model_copy(deep=True)
    return default,"@default",list(dict.fromkeys(primary.warnings+["chưa có video mẫu cho danh mục này"]))


def load_token(settings,preset):
    if preset=="@default":
        return default_profile(settings)
    parts=preset.split(":")
    if len(parts) not in (2,3) or parts[0]!="@category":
        raise ValueError("Mã hồ sơ danh mục không hợp lệ.")
    profile,_,_=resolve_profile(settings,parts[1],parts[2] if len(parts)==3 else None)
    return profile


def choose_profile(settings,category=None,preset=None,video_type=None):
    if preset=="none":
        return None,None,[]
    if preset:
        if preset.startswith("@category:") and len(preset.split(":"))==2 and video_type:
            return resolve_profile(settings,preset.split(":")[1],video_type)
        from pipeline.style_profile import load_profile
        profile=load_profile(settings,preset)
        return profile,preset,list(profile.warnings)
    if category:
        return resolve_profile(settings,category,video_type)
    return None,None,[]


def save_category_edits(settings,category,*,reusable_rules,connective_phrases,locked_fields,video_type=None):
    profile=rebuild_category(settings,category,video_type=video_type)
    if any(name not in {"reusable_rules","connective_phrases"} for name in locked_fields):
        raise ValueError("Chỉ khóa quy tắc và cụm nối.")
    profile.reusable_rules=list(dict.fromkeys(r.strip() for r in reusable_rules if r.strip()))
    profile.connective_phrases=list(dict.fromkeys(r.strip() for r in connective_phrases if r.strip()))[:12]
    from pipeline.style_profile import key
    allowed={key(p) for p in profile.connective_phrases}
    profile.connective_frequencies=[f for f in profile.connective_frequencies if key(f.rule) in allowed]
    profile.locked_fields=list(locked_fields)
    from pipeline.style_safety import sanitize_profile
    profile=sanitize_profile(StyleProfile.model_validate(profile.model_dump(mode="json")))
    path=profile_file(settings,category,video_type)
    with file_lock(path.with_suffix(".lock"),timeout=1):
        write_json_atomic(path,profile.model_dump(mode="json"))
    return profile


def profile_blueprint(duration,fact_count,profile):
    """Adapt the duration table without inventing content or breaking shot bounds."""
    table=min(profile.scene_pacing,key=lambda row:abs(row.duration_sec-duration))
    proposed=round(table.scene_count*duration/table.duration_sec)
    total=min(max(2,proposed),max(2,fact_count*2),max(2,int(duration/1.5)))
    times=durations_for_count(table.durations_sec,total,duration)
    # Hook remains <=3 seconds; retain the rest of the observed rhythm.
    surplus=max(0.,times[0]-3)
    times[0]-=surplus
    remaining=sum(times[1:])
    times[1:]=[t+surplus*t/remaining for t in times[1:]]
    patterns=profile.scene_patterns or profile.structure
    rows=[]
    for index,length in enumerate(times):
        count=max(1,math.ceil(length/min(4.,max(1.5,profile.shot_seconds.mean)) - 1e-9))
        count=min(max(count,math.ceil(length/4 - 1e-9)),max(1,math.floor(length/1.5+1e-9)))
        shots=[length/count]*count;shots[-1]=length-sum(shots[:-1])
        pattern=patterns[min(len(patterns)-1,int(index*len(patterns)/total))] if patterns else None
        purpose=getattr(pattern,"purpose",getattr(pattern,"name","nội dung"))
        rows.append({"id":index+1,"role":"hook" if index==0 else "cta" if index==total-1 else "body",
            "shot_durations_sec":shots,"pattern_interrupt":index>0 and index%2==0,"style_section":purpose,
            "connective_template":getattr(pattern,"connective_template",""),"transition_hint":getattr(pattern,"transition","cut")})
    return rows


def compare_plan(plan,profile):
    from pipeline.style_profile import key
    duration=plan.duration_sec
    table=min(profile.scene_pacing,key=lambda r:abs(r.duration_sec-duration)) if profile.scene_pacing else None
    shots=[s for scene in plan.scenes for s in scene.shots]
    text=key(" ".join(s.narration for s in plan.scenes))
    phrases=[]
    for phrase in profile.connective_phrases:
        fixed=key(phrase.split("{topic}")[0]).strip()
        phrases.append({"khuôn":phrase,"số lần":text.count(fixed) if fixed else 0})
    return {"summary":[{"chỉ số":"Số cảnh","kịch bản":len(plan.scenes),"hồ sơ":round(table.scene_count*duration/table.duration_sec) if table else len(profile.structure)},
        {"chỉ số":"Giây/cảnh","kịch bản":round(duration/len(plan.scenes),2),"hồ sơ":round(table.avg_scene_sec,2) if table else None},
        {"chỉ số":"Shot/10s","kịch bản":round(len(shots)/duration*10,2),"hồ sơ":round(profile.shots_per_10_sec,2)}],
        "scenes":[{"cảnh":s.id,"vai trò":s.role,"mục đích":s.style_purpose or s.role,"lời đọc":s.narration,"giây":round(s.duration_sec,2),"shot":len(s.shots)} for s in plan.scenes],
        "patterns":[p.model_dump(mode="json") for p in profile.scene_patterns],"phrases":phrases}
