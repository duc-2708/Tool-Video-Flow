"""One idempotent boundary for Gemini's parallel shot arrays and saved plans."""
from copy import deepcopy
import math
from pydantic import BaseModel


def normalize_plan_structure(plan, *, reference=None, diagnostics=None, query_provider=None, unique_queries=True):
    """Preserve narration/facts/timing; pad/truncate presentation arrays only.

    Reference is a plan or the code-generated blueprint. Word/outline responses
    keep their own schema; full plans consume parallel arrays into shot objects.
    Accept dicts before Pydantic and models at final validation/Assets boundaries.
    """
    model=plan if isinstance(plan,BaseModel) else None
    data=deepcopy(plan.model_dump(mode="json") if model else plan)
    ref=reference.model_dump(mode="json") if isinstance(reference,BaseModel) else reference
    refs=ref.get("scenes",[]) if isinstance(ref,dict) else ref if isinstance(ref,list) else []
    by_id={r.get("id",r.get("scene_id")):r for r in refs if isinstance(r,dict)}
    if not isinstance(data,dict): return data
    if isinstance(data.get("plan"),dict):
        data["plan"]=normalize_plan_structure(data["plan"],reference=reference,diagnostics=diagnostics,query_provider=query_provider,unique_queries=unique_queries)
        return data
    from agents.broll_queries import sanitize_broll_query,unique_query
    updated={s.get("id",s.get("scene_id")) for s in data.get("scenes",[]) if isinstance(s,dict)}
    used={s.get("query") for r in refs if r.get("id",r.get("scene_id")) not in updated for s in r.get("shots",[]) if s.get("query")}
    for scene in data.get("scenes",[]):
        if not isinstance(scene,dict): continue
        sid=scene.get("id",scene.get("scene_id"))
        source=by_id.get(sid,{})
        full="id" in scene and ("narration" in scene or "shots" in scene)
        words="scene_id" in scene and ("narration" in scene or "overlays" in scene)
        notices=[]
        def warn(message):
            text=f"Cảnh {sid}: chuẩn hóa cấu trúc — "+message
            if text not in notices: notices.append(text)
        narrative=str(scene.get("narration",source.get("narration",""))).casefold()
        query=next((q for token,q in [("video","video editing"),("công nghệ","technology detail"),("máy","technology detail"),
            ("du lịch","travel landscape"),("sức khỏe","healthy lifestyle"),("thể thao","sports training")] if token in narrative),"news detail")
        shots=scene.get("shots")
        if isinstance(shots,list):
            shots=[s.model_dump(mode="json") if isinstance(s,BaseModel) else s for s in shots]
            scene["shots"]=shots
        if full and not shots:
            durations=source.get("shot_durations_sec") or [s.get("duration_sec",3.) for s in (source.get("shots") or [])]
            if not durations:
                duration=scene.get("duration_sec",3.)
                if not isinstance(duration,(float,int)) or not math.isfinite(duration): duration=3.
                duration=max(1.5,float(duration))
                count=max(1,math.ceil(duration/4.))
                durations=[duration/count]*count
            shots=[{"type":"stock_video","query":query,"duration_sec":d,"effect":"none","text_overlay":None} for d in durations]
            scene["shots"]=shots
            scene.pop("duration_sec",None)
            warn(f"không có shot; tạo {len(shots)} shot mặc định từ ngữ cảnh, giữ thời lượng tham chiếu nếu có")
        n=len(shots) if isinstance(shots,list) and shots else len(source.get("shots") or []) or len(source.get("shot_durations_sec") or [])
        if not n and words:
            n=max(1,len(scene.get("overlays") or []))
        if not (full or words):
            # Outline has fact mappings, not render shots. Never invent facts.
            continue
        mappings=[("overlays",("overlays","on_screen_texts"),None),
            ("shot_queries",("shot_queries","broll_queries","queries"),query),
            ("shot_effects",("shot_effects","effects"),"none"),
            ("shot_types",("shot_types","types"),"stock_video"),
            ("shot_sfx",("shot_sfx",),"none")]
        # Some models put arrays in fields which are normally scalar.
        for scalar,array in [("broll_query","shot_queries"),("effect","shot_effects"),("type","shot_types"),("sfx","shot_sfx")]:
            if isinstance(scene.get(scalar),list): scene[array]=scene.pop(scalar)
        arrays={}
        for name,aliases,default in mappings:
            found=next((key for key in aliases if key in scene),None)
            if found is None and name!="overlays": continue
            if found is None and full: continue
            value=scene.get(found) if found else []
            value=value if isinstance(value,list) else [] if value is None else [value]
            before=len(value)
            value=value[:n]+[default]*max(0,n-before)
            if name=="overlays": value=[v if isinstance(v,str) and v.strip() else None for v in value]
            if before!=n: warn(f"{name}: {before} → {n}; "+("điền giá trị mặc định" if before<n else "cắt phần thừa, không gộp thành overlay dài"))
            arrays[name]=value
            for alias in aliases: scene.pop(alias,None)
            if words: scene[name]=value
        if full:
            for i,shot in enumerate(shots):
                if "on_screen_text" in shot:
                    shot.setdefault("text_overlay",shot.pop("on_screen_text"))
                if "source" in shot:
                    shot.setdefault("type",shot.pop("source"))
                if "overlays" in arrays: shot["text_overlay"]=arrays["overlays"][i]
                for name,field in [("shot_queries","query"),("shot_effects","effect"),("shot_types","type")]:
                    if name in arrays: shot[field]=arrays[name][i]
                shot.setdefault("text_overlay",None)
                for field,allowed,default in [("effect",{"none","zoom_in","zoom_out","pan_left","pan_right"},"none"),
                    ("type",{"stock_video","stock_image","ai_image","ai_video","text_card"},"stock_video")]:
                    if shot.get(field) not in allowed:
                        shot[field]=default;warn(f"shot {i+1}: dùng {field}={default} hợp lệ")
                try: seconds=float(shot.get("duration_sec",3))
                except (ValueError,TypeError): seconds=3.
                seconds=min(600. if shot.get("planning_duration") else 4.,max(1/30 if shot.get("planning_duration") else 1.5,seconds)) if math.isfinite(seconds) else 3.
                if seconds!=shot.get("duration_sec"):
                    shot["duration_sec"]=seconds;warn(f"shot {i+1}: duration_sec={seconds:g} hợp lệ")
            if scene.get("sfx") not in {"none","whoosh","pop"}:
                scene["sfx"]="none";warn("sfx thiếu/không hợp lệ: dùng none")
            if scene.get("transition_out") not in {"cut","fade","zoom","whip"}:
                scene["transition_out"]="cut";warn("transition_out thiếu/không hợp lệ: dùng cut")
            if scene.get("role") not in {"hook","body","transition","cta"}:
                scene["role"]="body";warn("role thiếu/không hợp lệ: dùng body")
            if "shot_sfx" in arrays:
                scene["sfx"]=next((v for v in arrays["shot_sfx"] if v!="none"),"none")
                warn("shot_sfx đồng bộ theo shot và quy về SFX cấp cảnh theo hợp đồng renderer")
            if notices:
                notes=scene.get("review_notes") or {"fact_ids":scene.get("fact_ids",[]),"source_count":0,"confidence":None,"facts":[]}
                notes["warnings"]=list(dict.fromkeys(notes.get("warnings",[])+notices))
                scene["review_notes"]=notes
        else:
            scene.pop("shots",None)
            scene.setdefault("broll_query",next((q for q in arrays.get("shot_queries",[]) if q),source.get("broll_query",query)))
            scene["structure_warnings"]=list(dict.fromkeys(scene.get("structure_warnings",[])+notices))
            if not scene["structure_warnings"]: scene.pop("structure_warnings")
        # Expand scalar scene queries into independent stock slots before schema validation.
        raw_queries=[s.get("query","") for s in shots] if full else scene.get("shot_queries") or [scene.get("broll_query","")]*n
        clean_queries=[]
        for i,old in enumerate(raw_queries):
            if full and shots[i].get("semantic_query"):
                from agents.explainer_visuals import semantic_query
                clean=semantic_query(old,narrative)
                shots[i]["query"]=clean;clean_queries.append(clean);used.add(clean)
                continue
            # Group 2 policy: validation repairs never spend another Gemini call.
            clean=sanitize_broll_query(old,narrative,diagnostics=diagnostics)
            if unique_queries: clean=unique_query(clean,narrative,used)
            used.add(clean);clean_queries.append(clean)
            if clean!=old:
                message=f"Cảnh {sid}, shot {i+1}: sửa b-roll query {old!r} → {clean!r}"
                if diagnostics: message=diagnostics.redact(message)
                notices.append(message)
            if full: shots[i]["query"]=clean
        if words:
            scene["shot_queries"]=clean_queries
            scene["broll_query"]=clean_queries[0] if clean_queries else query
            scene["structure_warnings"]=list(dict.fromkeys(scene.get("structure_warnings",[])+notices))
            if not scene["structure_warnings"]: scene.pop("structure_warnings")
        elif notices:
            notes=scene.get("review_notes") or {"fact_ids":scene.get("fact_ids",[]),"source_count":0,"confidence":None,"facts":[]}
            notes["warnings"]=list(dict.fromkeys(notes.get("warnings",[])+notices));scene["review_notes"]=notes
        if diagnostics:
            for notice in notices: diagnostics.record(notice)
    if model:
        parsed=type(model).model_validate(data)
        for name in type(model).model_fields: setattr(model,name,getattr(parsed,name))
        return model
    return data
