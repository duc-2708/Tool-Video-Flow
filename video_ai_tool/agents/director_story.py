"""Three checked passes; deterministic timing and locked fact IDs."""
import json
import math
from pathlib import Path
from config.storytelling import STYLE_GUIDES
from agents.story_style import story_blueprint, style_issues, data_advice
from agents.adaptive import fact_schedule
from agents.plan_structure import normalize_plan_structure
from schemas.story import StoryOutline, WrittenScript, HumanizedScript
from schemas.edit_plan import EditPlan,Shot
from utils.cache import cache_key, write_json


def template(settings,name):
    return (settings.prompts_dir/name).read_text(encoding="utf-8")


def validate_outline(outline,brief,blueprint,diagnostics=None):
    from agents.validation_rules import run_rules
    return run_rules(outline,brief,phase="outline",blueprint=blueprint,diagnostics=diagnostics)


def check_words(rows,expected):
    actual = [row.scene_id for row in rows]
    if len(actual)!=len(set(actual)) or set(actual)!=set(expected):
        from agents.validation_rules import RuleViolation
        from schemas.validation import ValidationEvent
        failed=set(expected)-set(actual) or set(actual)-set(expected)
        raise RuleViolation([ValidationEvent(rule_id="schema_basic",group=1,scene_id=i,action="error",message="Lượt viết thiếu/trùng/ngoài ID cảnh được yêu cầu.") for i in failed or set(expected)])


def apply_words(plan,rows,diagnostics=None):
    normalized=normalize_plan_structure({"scenes":[r.model_dump(mode="json") for r in rows]},reference=plan,diagnostics=diagnostics)
    from schemas.story import SceneWords
    from schemas.edit_plan import ReviewNotes
    for data in normalized["scenes"]:
        row=SceneWords.model_validate(data)
        scene = next(s for s in plan.scenes if s.id==row.scene_id)
        if not scene.shots: normalize_plan_structure(plan,diagnostics=diagnostics)
        scene = next(s for s in plan.scenes if s.id==row.scene_id)
        # Lists have already been aligned; indexing cannot truncate the timeline.
        shots=[Shot.model_validate({**shot.model_dump(mode="json"),"text_overlay":row.overlays[i] or None,
            "query":row.shot_queries[i] if row.shot_queries else row.broll_query,
            "effect":row.shot_effects[i] if row.shot_effects else shot.effect,
            "type":row.shot_types[i] if row.shot_types else shot.type}) for i,shot in enumerate(scene.shots)]
        scene.narration = row.narration
        scene.shots=shots
        for i,shot in enumerate(shots):
            if i<len(row.card_texts): shot.card_text=row.card_texts[i]
            if i<len(row.emphasis): shot.emphasis=row.emphasis[i]
        if row.shot_sfx: scene.sfx=next((s for s in row.shot_sfx if s!="none"),"none")
        if row.structure_warnings:
            if scene.review_notes is None:
                scene.review_notes=ReviewNotes(fact_ids=scene.fact_ids,source_count=0,confidence=None,facts=[])
            scene.review_notes.warnings=list(dict.fromkeys(scene.review_notes.warnings+row.structure_warnings))
            plan.review_notes=list(dict.fromkeys(plan.review_notes+row.structure_warnings))


def humanize(plan,brief,provider,settings,diagnostics,*,scene_ids=None,style=None):
    from agents.director import validate_plan, DirectorRequest, DirectorDraftError, director_facts
    from agents.validation_rules import RuleViolation,run_rules,audit_findings,schema_events,Finding,emit,RULES,groups,Context
    from pydantic import ValidationError
    plan=plan.model_copy(deep=True)
    plan.script_style=style or plan.script_style or "storytelling"
    request=DirectorRequest(video_type=plan.video_type or "story",video_format=plan.format,duration_sec=max(6,plan.requested_duration_sec or plan.target_duration_sec or plan.duration_sec))
    baseline=plan.model_copy(deep=True)
    baseline_error=None
    try: validate_plan(baseline,brief,request,check_style=False,diagnostics=diagnostics,allow_merge=False)
    except RuleViolation as error: baseline_error=error
    selected=set(scene_ids) if scene_ids is not None else {s.id for s in plan.scenes}
    requested=set(selected);baseline_rejected=set();feedback={};last=None
    for attempt in range(3):
        from pipeline.style_profile import guidance,speech_budget
        from agents.director_sources import allowed_sources
        payload={"allowed_sources":allowed_sources(brief),"style_profile":guidance(plan.style_profile),"creative_license":plan.creative_license,"style":STYLE_GUIDES[plan.script_style],"facts":director_facts(brief),
            "outline":plan.story_outline.model_dump(mode="json") if plan.story_outline else None,
            "selected_scene_ids":sorted(selected),"full_plan":plan.model_dump(mode="json",exclude={"style_profile","render_style","style_preset"}),"feedback":feedback,
            "speech_budget":speech_budget(plan.duration_sec,plan.style_profile)}
        prompt=template(settings,"director_common.txt")+"\n"+template(settings,"director_humanize.txt")+"\nINPUT_DATA_JSON:\n"+json.dumps(payload,ensure_ascii=False)
        normalized=None
        try:
            raw=provider.generate_json(prompt,HumanizedScript)
            normalized=normalize_plan_structure(json.loads(raw),reference=plan,diagnostics=diagnostics)
            result=HumanizedScript.model_validate(normalized)
            check_words(result.scenes,selected)
            for row in result.scenes: apply_words(plan,[row],diagnostics)
            from agents.presentation import humanize_locally,repair_generic_hook
            humanize_locally(plan,brief);repair_generic_hook(plan,brief)
            validate_plan(plan,brief,request,diagnostics=diagnostics,allow_merge=False)
            audit=audit_findings(result.issues)
            if not result.approved and not result.issues:
                audit=[("audit_clarity",Finding(None,"Audit từ chối nhưng không chỉ rõ lỗi căn cứ; giữ bản kiểm tra bằng code."))]
            for key,finding in audit:
                if key!="grounding_claims" or finding.scene_id not in selected: continue
                current=next(s for s in plan.scenes if s.id==finding.scene_id)
                original=next(s for s in baseline.scenes if s.id==finding.scene_id)
                if current.narration==original.narration and [s.text_overlay for s in current.shots]==[s.text_overlay for s in original.shots]: baseline_rejected.add(finding.scene_id)
            run_rules(plan,brief,request,diagnostics=diagnostics,audit_issues=audit,allow_merge=False)
            return plan
        except (ValidationError,json.JSONDecodeError) as error:
            last=RuleViolation(schema_events(error,normalized,"humanize"))
        except RuleViolation as error:
            last=error
        except Exception as error:
            from providers.llm.base import TransientError
            if isinstance(error,TransientError): raise
            diagnostics.record_exception(error,"Người hóa/API không phải lỗi luật nhóm 1; không retry văn phong")
            break
        diagnostics.record_exception(last,f"Người hóa lần {attempt+1}: chỉ retry nhóm 1")
        if not last.scene_ids and any(e.rule_id!="schema_basic" for e in last.events): break
        selected=last.scene_ids or selected
        feedback={scene_id:[e.message for e in last.events if e.scene_id in {None,scene_id}] for scene_id in selected}
        diagnostics.record(f"Người hóa lần {attempt+1}: đối tượng=cảnh {sorted(selected)}, luật nhóm 1={feedback}")
    # Fallback is permitted only to an independently code-checked baseline.
    if baseline_error is None and not (selected & baseline_rejected):
        original={s.id:s for s in baseline.scenes}
        plan.scenes=[original[s.id].model_copy(deep=True) if s.id in selected else s for s in plan.scenes]
        plan.humanization_fallback_scene_ids=sorted(set(plan.humanization_fallback_scene_ids)|selected)
        message=f"Người hóa chưa đạt ở cảnh {sorted(selected)}; dùng lời đọc lượt 2 đã qua kiểm tra căn cứ."
        if message not in plan.review_notes: plan.review_notes.append(message)
        validate_plan(plan,brief,request,diagnostics=diagnostics)
        for scene in plan.scenes:
            if scene.id in selected and message not in scene.review_notes.warnings: scene.review_notes.warnings.append(message)
        diagnostics.record(message)
        return plan
    error=DirectorDraftError("Nhóm 1 chưa đạt sau retry riêng cảnh: "+str(last or baseline_error))
    error.failed_scene_ids=sorted(selected)
    error.validation_errors=[e.model_dump(mode="json") for e in (last or baseline_error).events]
    error.draft_plan=plan.model_dump(mode="json")
    raise error


def create_story_plan(brief,request,provider,settings,cache,diagnostics,progress,*,draft_path=None):
    from agents.director import director_facts,brief_hash,validated_json,DirectorDraftError,validate_plan
    from pipeline.style_profile import guidance,apply_defaults,speech_budget
    from agents.director_sources import allowed_sources
    blueprint = story_blueprint(request.duration_sec,len(brief.facts),request.style_profile)
    data = {"allowed_sources":allowed_sources(brief),"style_profile":guidance(request.style_profile),"discovery_hint":brief.discovery_hint.model_dump(mode="json") if brief.discovery_hint else None,"topic":brief.topic,"request":request.model_dump(mode="json"),"facts":director_facts(brief),
        "angles":[a.model_dump(mode="json") for a in (brief.story_angles or brief.angle_candidates)],
        "blueprint":blueprint,"suggested_fact_ids_by_scene":fact_schedule(blueprint,len(brief.facts)),"creative_license":request.creative_license,"style":STYLE_GUIDES[request.script_style],"voice":settings.default_voice,
        "speech_budget":speech_budget(request.duration_sec,request.style_profile)}
    prompts = [template(settings,name) for name in ("director_common.txt","director_outline.txt","director_write.txt","director_humanize.txt",f"director_{request.video_type}.txt")]
    from agents.validation_rules import groups
    key = {"validation_policy":groups(),"style_profile_hash":cache_key(request.style_profile.model_dump(mode="json")) if request.style_profile else None,"data":data,"model":provider.model_name,"prompts":cache_key(prompts),"version":7}
    cached = cache.get("director-story-v1",key)
    if isinstance(cached,dict) and cached.get("approved") is True and isinstance(cached.get("plan"),dict):
        if cached.get("audit_plan_hash")==cache_key(cached["plan"]):
            return validate_plan(EditPlan.model_validate(cached["plan"]),brief,request)
    from agents.director_state import DirectorState
    state_path=(draft_path or settings.output_dir/"edit_plan.draft.json").with_name("director_state.json")
    state=DirectorState(state_path,key,diagnostics,progress)
    advice = data_advice(brief,request.duration_sec)
    if advice["thin"]: progress(advice["warning"]+f"; đề xuất {advice['suggested_duration']:g} giây.")
    plan = None
    candidate = None
    stage="outline"
    try:
        progress("Lượt 1/3: chọn góc kể, dàn ý và open loop…")
        prompt = prompts[0]+"\n"+prompts[1]+"\nINPUT_DATA_JSON:\n"+json.dumps(data,ensure_ascii=False)
        outline = state.load("outline",StoryOutline)
        if outline is not None:
            try: validate_outline(outline,brief,blueprint,diagnostics)
            except ValueError:
                state.invalidate_from("outline");outline=None
        repair_ids=set()
        for attempt in range(3):
            if outline is None:
                outline = validated_json(provider,prompt,StoryOutline,1,diagnostics,reference=blueprint)
            elif repair_ids:
                from schemas.story import OutlineRepairs
                fixed=validated_json(provider,prompt,OutlineRepairs,1,diagnostics,reference=blueprint)
                by_id={s.scene_id:s for s in fixed.scenes if s.scene_id in repair_ids}
                outline.scenes=[by_id.get(s.scene_id,s) for s in outline.scenes]
            try:
                validate_outline(outline,brief,blueprint,diagnostics)
                break
            except ValueError as error:
                if attempt==2: raise
                diagnostics.record_exception(error,"Kiểm tra dàn ý")
                repair_ids=set(getattr(error,"scene_ids",[]))
                if not repair_ids: raise
                prompt=(prompts[0]+"\nChỉ sửa fact_ids/cảnh lỗi nhóm 1 trong OutlineRepairs; không đổi cảnh đã đạt.\nINPUT_DATA_JSON:\n"+
                    json.dumps({"allowed_sources":allowed_sources(brief),"selected_scene_ids":sorted(repair_ids),"scenes":[s.model_dump() for s in outline.scenes if s.scene_id in repair_ids],"facts":director_facts(brief),"errors":str(error)},ensure_ascii=False))
        state.save("outline",outline)
        stage="written"
        progress("Lượt 2/3: viết lời đọc theo dàn ý đã kiểm tra…")
        data = {**data,"outline":outline.model_dump(mode="json")}
        written = state.load("written",WrittenScript)
        if written is not None:
            try: check_words(written.scenes,[r["id"] for r in blueprint])
            except ValueError:
                state.invalidate_from("written");written=None
        if written is None:
            written = validated_json(provider,prompts[0]+"\n"+prompts[4]+"\n"+prompts[2]+"\nINPUT_DATA_JSON:\n"+json.dumps(data,ensure_ascii=False),WrittenScript,3,diagnostics,reference=blueprint)
        check_words(written.scenes,[r["id"] for r in blueprint])
        state.save("written",written)
        facts = {r.scene_id:r.fact_ids for r in outline.scenes}
        words = {r.scene_id:r for r in written.scenes}
        scenes = []
        for row in blueprint:
            word = words[row["id"]]
            scenes.append({"id":row["id"],"role":row["role"],"style_purpose":row.get("style_section"),"narration":word.narration,"fact_ids":facts[row["id"]],
                "pattern_interrupt":row["pattern_interrupt"],"transition_out":"zoom" if row["pattern_interrupt"] else "cut","sfx":"none",
                "shots":[{"type":"stock_video","query":word.shot_queries[i] if word.shot_queries else word.broll_query,"duration_sec":seconds,
                    "effect":"zoom_in" if row["pattern_interrupt"] else "pan_left","text_overlay":None} for i,seconds in enumerate(row["shot_durations_sec"])]})
        candidate={"title":written.title,"format":request.video_format,"voice":settings.default_voice,
            "music":{"mood":"calm","volume":.08},"scenes":scenes,"video_type":request.video_type,"target_duration_sec":request.duration_sec,
            "brief_hash":brief_hash(brief),"adaptive":True,"requested_duration_sec":request.requested_duration_sec or request.duration_sec,"creative_license":request.creative_license,"script_style":request.script_style,"story_outline":outline.model_dump(mode="json"),"validation_events":[e.model_dump(mode="json") for e in outline.validation_events]}
        candidate=normalize_plan_structure(candidate,diagnostics=diagnostics,query_provider=provider)
        plan = EditPlan.model_validate(candidate)
        apply_defaults(plan,request.style_profile)
        apply_words(plan,written.scenes,diagnostics)
        try:
            validate_plan(plan,brief,request,check_style=False,check_title=False,diagnostics=diagnostics,allow_merge=False)
        except ValueError as error:
            diagnostics.record_exception(error,"Lượt 2: chuyển lỗi lời đọc cho lượt người hóa, chưa lưu bản cuối")
        progress("Lượt 3/3: người hóa lời đọc và audit căn cứ của bản cuối…")
        stage="humanized"
        completed=state.load("humanized",EditPlan)
        plan = completed if completed is not None else humanize(plan,brief,provider,settings,diagnostics)
        validate_plan(plan,brief,request,check_title=False,diagnostics=diagnostics)
        state.save("humanized",plan)
        approved_plan = plan.model_dump(mode="json")
        cache.set("director-story-v1",key,{"plan":approved_plan,"approved":True,"audit_plan_hash":cache_key(approved_plan)})
        return plan
    except Exception as error:
        state.failed(stage,error)
        diagnostics.record_exception(error,"Director ba lượt")
        path = draft_path or settings.output_dir/"edit_plan.draft.json"
        from agents.content_plan import draft_presentation
        draft_data=draft_presentation(getattr(error,"draft_plan",plan.model_dump(mode="json") if plan else candidate),brief,request,diagnostics)
        write_json(path,{"plan":draft_data,
            "warnings":[diagnostics.redact(str(error))],"failed_scene_ids":getattr(error,"failed_scene_ids",list(getattr(error,"scene_ids",[]))),
            "validation_errors":getattr(error,"validation_errors",[e.model_dump(mode="json") for e in getattr(error,"events",[])]),"status":"draft_requires_review"})
        raise DirectorDraftError(f"Director chưa đạt; bản nháp: {path}. "+diagnostics.redact(str(error))) from error


def rewrite_script(brief_path,settings,*,style,scene_id=None):
    from agents.director import director_provider,director_diagnostics,validate_plan,DirectorRequest,resolve_draft
    from pipeline.projects import read_json
    from schemas.research_brief import ResearchBrief
    from utils.file_lock import file_lock
    brief_path = Path(brief_path)
    diagnostics = director_diagnostics(settings)
    with file_lock(brief_path.parent/"run_all.lock",timeout=0):
        plan = EditPlan.model_validate(read_json(brief_path.parent/"edit_plan.json"))
        brief = ResearchBrief.model_validate(read_json(brief_path))
        if scene_id is not None and scene_id not in {s.id for s in plan.scenes}: raise ValueError("Cảnh không tồn tại.")
        provider = director_provider(settings,diagnostics)
        try:
            if plan.content_mode=="explainer_v2":
                from agents.explainer_director import rewrite_explainer
                rewritten=rewrite_explainer(plan,brief,provider,settings,diagnostics,scene_id=scene_id,style=style)
            else:
                rewritten = humanize(plan,brief,provider,settings,diagnostics,scene_ids=[scene_id] if scene_id is not None else None,style=style)
            # A local voice change does not relabel the whole video's style.
            if scene_id is not None:
                rewritten.script_style = plan.script_style
            # Scene-only rewrite keeps every other scene byte-for-byte.
            if scene_id is None:
                validate_plan(rewritten,brief,DirectorRequest(video_type=rewritten.video_type or "story",video_format=rewritten.format,duration_sec=rewritten.target_duration_sec or rewritten.duration_sec))
            from providers.llm.router import add_provider_notes
            add_provider_notes(rewritten,provider)
            write_json(brief_path.parent/"edit_plan.json",rewritten.model_dump(mode="json"))
            resolve_draft(brief_path.parent)
            return brief_path.parent/"edit_plan.json"
        finally: provider.close()
