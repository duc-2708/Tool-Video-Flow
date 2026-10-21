# file: agents/director.py
"""Director dùng chung CLI/UI: brief có nguồn → kế hoạch đã kiểm tra."""
import argparse
import json
import logging
import math
import re
import unicodedata
from pathlib import Path
from typing import Callable, Literal
from urllib.parse import urlsplit
from pydantic import Field, ValidationError, model_validator
from config.settings import Settings, get_settings
from pipeline.projects import read_json
from providers.llm_base import LLMProvider,ProviderError
from providers.llm_gemini import GeminiOutputError, GeminiProvider
from schemas.base import StrictModel
from schemas.edit_plan import EditPlan, Scene, ReviewNotes, FactReview, ReviewSource
from schemas.research_brief import ResearchBrief
from utils.cache import JsonCache, cache_key, write_json
from utils.console import configure_console
from utils.diagnostics import Diagnostics
from utils.source_credits import publisher_name
from schemas.languages import LanguageOptions
from agents.video_prompt_writer import fill_plan_prompts,validate_ai_prompt
from agents.script_depth import validate_script_depth,speech_budget
from agents.director_numbers import normalized_numbers
from agents.plan_structure import normalize_plan_structure


class DirectorError(RuntimeError):
    """Lỗi Director hiển thị được, không chứa credentials."""


class DirectorDraftError(DirectorError):
    pass


class SceneRepairs(StrictModel):
    scenes: list[Scene]


def resolve_draft(project):
    path = project/"edit_plan.draft.json"
    if path.exists():
        draft = read_json(path)
        draft["status"] = "resolved"
        write_json(path,draft)


def fill_missing_facts(plan,brief,diagnostics):
    bodies = [scene for scene in plan.scenes if scene.role == "body"]
    required = 1
    used = {index for scene in plan.scenes for index in scene.fact_ids}
    for scene in bodies:
        while len(set(scene.fact_ids))<required:
            available = [index for index in range(1,len(brief.facts)+1) if index not in used]
            if not available:
                break
            text = scene.narration.casefold()
            index = max(available,key=lambda index:len(set(text.split()) & set(vietnamese_fact(brief.facts[index-1]).casefold().split())))
            if not set(text.split()) & set(vietnamese_fact(brief.facts[index-1]).casefold().split()): break
            scene.fact_ids.append(index)
            used.add(index)
            diagnostics.record(f"Cảnh {scene.id}: luật thiếu fact, cần={required}, thực tế={len(scene.fact_ids)}; tự gán fact #{index}, vẫn phải qua audit ngữ nghĩa.")


def failing_scene_ids(error,data):
    if hasattr(error,"scene_ids"): return error.scene_ids
    if str(error).startswith("Tiêu đề"):
        return set()
    ids = set(int(index) for index in re.findall(r"[Cc]ảnh\s*#?\s*(\d+)",str(error)))
    scenes = data.get("scenes",[]) if isinstance(data,dict) else []
    if isinstance(error,ValidationError):
        for item in error.errors(include_input=False):
            loc = item["loc"]
            if len(loc)>1 and loc[0] == "scenes" and isinstance(loc[1],int) and loc[1]<len(scenes):
                ids.add(scenes[loc[1]].get("id",loc[1]+1))
    return ids or {scene["id"] for scene in scenes if isinstance(scene,dict) and "id" in scene}


from schemas.style import StyleProfile


class DirectorRequest(StrictModel):
    style_preset: str | None = None
    style_profile: StyleProfile | None = Field(default=None, exclude=True)
    video_type: Literal["news", "review", "story"]
    video_format: Literal["tiktok", "youtube"]
    duration_sec: float = Field(ge=6, le=600)
    output_language: Literal["vi"] = "vi"
    script_style: Literal["storytelling", "news", "explain", "review"] | None = "storytelling"
    creative_license: Literal["strict","balanced","story"] = "strict"
    requested_duration_sec: float | None = None


class GroundingAudit(StrictModel):
    approved: bool
    issues: list[str]

    @model_validator(mode="after")
    def consistent(self):
        if self.issues: self.approved=False
        elif not self.approved: self.issues=["[audit_clarity] Audit không chỉ rõ lỗi; giữ kiểm tra căn cứ bằng code."]
        return self


def brief_hash(brief: ResearchBrief) -> str:
    data = brief.model_dump(mode="json")
    # Old Vietnamese projects remain editable without rewriting their brief.
    if not brief.search_queries and all(fact.fact_vi is None for fact in brief.facts):
        data.pop("source_languages",None)
        data.pop("output_language",None)
        for fact in data["facts"]:
            if fact.get("source_lang") == "vi":
                fact.pop("source_lang",None)
    return cache_key(data)


def vietnamese_fact(fact):
    if fact.fact_vi:
        return fact.fact_vi
    if fact.source_lang == "vi":
        return fact.claim  # Legacy Vietnamese brief only.
    raise DirectorError("Fact nguồn nước ngoài thiếu fact_vi. Chạy Researcher lại; không tự dịch quote thành lời đọc.")


def director_facts(brief):
    return [dict(id=i,fact_vi=vietnamese_fact(fact),source_name=fact.source_name if fact.fact_vi else publisher_name(fact.source_url),
        source_url=str(fact.source_url),source_lang=fact.source_lang,published_at=fact.published_at,
        pronunciation_hint=fact.pronunciation_hint,source_review=fact_review(i,brief).model_dump(mode="json"))
        for i,fact in enumerate(brief.facts,1)]


def numbers(text: str) -> set[str]:
    return normalized_numbers(text)


FORBIDDEN_EDITORIAL = r"chưa\s+(?:được\s+)?(?:kiểm\s+chứng|xác\s+minh)|cần\s+xác\s+minh"


def source_domain(url: str) -> str:
    """Use the URL's domain, not a model-invented newspaper name."""
    host = (urlsplit(str(url)).hostname or "").lower()
    return host.removeprefix("www.")


def claim_identity(claim: str) -> str:
    # Only identical normalized claims are grouped. Different claims in a scene
    # do NOT prove that each individual claim has multiple sources.
    return " ".join(unicodedata.normalize("NFC", claim).casefold().split()).rstrip(".!?。")


def fact_review(fact_id: int, brief: ResearchBrief) -> FactReview:
    fact = brief.facts[fact_id - 1]
    identity = claim_identity(vietnamese_fact(fact))
    sources = [ReviewSource(fact_id=index, name=other.source_name if other.fact_vi else publisher_name(other.source_url),
                           url=other.source_url, confidence=other.confidence)
               for index, other in enumerate(brief.facts, 1) if claim_identity(vietnamese_fact(other)) == identity]
    return FactReview(fact_id=fact_id, source_count=len({publisher_name(source.url) for source in sources}),
                      confidence=fact.confidence, sources=sources)


def has_attribution(text: str, domain: str) -> bool:
    pattern = r"\bTheo\s+" + re.escape(domain) + r"(?=$|[\s,;:.!?])"
    return bool(re.search(pattern, text, re.I))


def review_notes_for(fact_ids: list[int], brief: ResearchBrief) -> ReviewNotes:
    invalid=[i for i in fact_ids if type(i) is not int or not 1<=i<=len(brief.facts)]
    facts = [fact_review(fact_id, brief) for fact_id in fact_ids if fact_id not in invalid]
    order = {"low": 0, "medium": 1, "high": 2}
    return ReviewNotes(fact_ids=list(fact_ids),
        source_count=len({publisher_name(source.url) for fact in facts for source in fact.sources}),
        confidence=min((fact.confidence for fact in facts), key=order.get) if facts else None,
        facts=facts,warnings=[f"fact_id không tồn tại: {invalid}"] if invalid else [])


def apply_review_notes(scene, brief: ResearchBrief) -> None:
    """Recompute metadata from the brief; never trust AI/user source counts."""
    previous=list(scene.review_notes.warnings) if scene.review_notes else []
    scene.review_notes = review_notes_for(scene.fact_ids, brief)
    scene.review_notes.warnings=previous
    facts = scene.review_notes.facts
    required = {fact.sources[0].name for fact in facts if fact.source_count == 1}
    # A shared single source supports the whole scene. Add only an attribution,
    # never a new factual assertion or an uncertainty warning.
    if len(required) == 1 and all(fact.source_count == 1 for fact in facts):
        domain = next(iter(required))
        if not has_attribution(scene.narration, domain):
            scene.narration = f"Theo {domain}, " + scene.narration
    else:
        for domain in sorted(required):
            if not has_attribution(scene.narration, domain):
                scene.narration=f"Theo {domain}, "+scene.narration
    if facts and all(fact.source_count >= 2 for fact in facts):
        if any(has_attribution(scene.narration, source.name) for fact in facts for source in fact.sources):
            for fact in facts:
                for source in fact.sources: scene.narration=re.sub(r"\bTheo\s+"+re.escape(source.name)+r"[,\s]*","",scene.narration,flags=re.I)


def content_scene_count(target,fact_count):
    from agents.adaptive import content_count
    return content_count(target,fact_count)


def timing_blueprint(target: float, fact_count=None) -> list[dict]:
    """Tính lịch gợi ý bằng code để model không phải tự cộng thời lượng."""
    if fact_count is not None and target>=10.5:
        bodies = content_scene_count(target,fact_count)
        bodies = min(bodies,int((target-6)//1.5))
        duration = (target-6)/bodies
        schedule = [{"id":1,"role":"hook","shot_durations_sec":[3.],"pattern_interrupt":False}]
        for index in range(bodies):
            count = math.ceil(duration/3)
            shots = [duration/count]*count
            shots[-1] = duration-sum(shots[:-1])
            schedule.append({"id":index+2,"role":"body","shot_durations_sec":shots,"pattern_interrupt":True})
        schedule.append({"id":bodies+2,"role":"cta","shot_durations_sec":[3.],"pattern_interrupt":True})
        return schedule
    remaining = target - 3.0
    count = math.ceil(remaining / 3.0)
    durations = [round(remaining / count, 6)] * count
    durations[-1] = round(remaining - sum(durations[:-1]), 6)
    schedule = [{"id": 1, "role": "hook", "shot_durations_sec": [3.0], "pattern_interrupt": False}]
    elapsed, last_interrupt = 3.0, 0.0
    while durations:
        interrupt = elapsed - last_interrupt >= 7
        if interrupt:
            last_interrupt = elapsed
        budget = min(9.0, 10.0 - (elapsed - last_interrupt))
        group = []
        while durations and len(group) < 3 and sum(group) + durations[0] <= budget + 0.00001:
            group.append(durations.pop(0))
        if not group:
            group=[durations.pop(0)]
            interrupt=True
        schedule.append({"id": len(schedule) + 1, "role": "cta" if not durations else "body",
                         "shot_durations_sec": group, "pattern_interrupt": interrupt})
        elapsed += sum(group)
    return schedule


def validate_plan(plan: EditPlan, brief: ResearchBrief, request: DirectorRequest, *, check_style=True, check_title=True, diagnostics=None, validation_path=None, allow_merge=True) -> EditPlan:
    from agents.validation_rules import run_rules
    plan=normalize_plan_structure(plan,diagnostics=diagnostics)
    return run_rules(plan,brief,request,diagnostics=diagnostics,config_path=validation_path,check_style=check_style,allow_merge=allow_merge)


def validated_json(provider: LLMProvider, prompt: str, schema: type, attempts: int,
                   diagnostics: Diagnostics, *, reference=None):
    from agents.validation_rules import RuleViolation,schema_events
    last=None;candidate=None;repair_ids=set();base_prompt=prompt
    for attempt in range(1,attempts+1):
        try:
            raw=provider.generate_json(prompt,schema)
            normalized=normalize_plan_structure(json.loads(raw),reference=reference,diagnostics=diagnostics)
            if repair_ids and candidate and isinstance(normalized,dict):
                replacements={r.get("id",r.get("scene_id")):r for r in normalized.get("scenes",[]) if r.get("id",r.get("scene_id")) in repair_ids}
                candidate["scenes"]=[replacements.get(r.get("id",r.get("scene_id")),r) for r in candidate.get("scenes",[])]
            else: candidate=normalized
            return schema.model_validate(candidate)
        except GeminiOutputError as error:
            diagnostics.record_exception(error,f"Director output/schema_basic, attempt={attempt}")
            if not error.retryable: raise
            last=error
        except (ValidationError,json.JSONDecodeError) as error:
            last=RuleViolation(schema_events(error,candidate))
            diagnostics.record_exception(last,f"Director schema_basic, attempt={attempt}")
            repair_ids=last.scene_ids
            if repair_ids and isinstance(candidate,dict):
                prompt=("Sửa JSON/schema cơ bản cho RIÊNG các cảnh sau, giữ ID và các trường cấp video. Trả đúng schema đã cấp, scenes chỉ gồm cảnh được yêu cầu.\nINPUT_DATA_JSON:\n"+
                    json.dumps({"selected_scene_ids":sorted(repair_ids),"scenes":[r for r in candidate.get("scenes",[]) if r.get("id",r.get("scene_id")) in repair_ids],"errors":str(last)},ensure_ascii=False))
            else: prompt=base_prompt+"\nSửa JSON/schema cơ bản; không markdown. "+str(last)
    if isinstance(last,RuleViolation):
        last.draft_plan=candidate
        raise last
    raise DirectorError("Director không trả JSON hợp lệ sau số lần thử cho phép.") from last


def audit_plan(plan: EditPlan, brief: ResearchBrief, provider: LLMProvider, settings: Settings,
               cache: JsonCache, diagnostics: Diagnostics) -> None:
    template = (settings.prompts_dir / "director_audit.txt").read_text(encoding="utf-8")
    payload = {"facts": director_facts(brief),
               "plan": plan.model_dump(mode="json",exclude={"style_profile"})}
    inputs = {"data": payload, "model": provider.model_name, "prompt": cache_key(template)}
    cached = cache.get("director-audit-v2", inputs)
    if isinstance(cached, dict):
        try:
            if GroundingAudit.model_validate(cached).approved:
                return
        except ValidationError:
            pass
    audit = validated_json(provider, template + "\nINPUT_DATA_JSON:\n" + json.dumps(payload, ensure_ascii=False),
                           GroundingAudit, settings.retry_attempts, diagnostics)
    if not audit.approved:
        from agents.validation_rules import run_rules,audit_findings
        run_rules(plan,brief,diagnostics=diagnostics,audit_issues=audit_findings(audit.issues),allow_merge=False)
    cache.set("director-audit-v2", inputs, audit.model_dump(mode="json"))


def create_edit_plan(brief: ResearchBrief, request: DirectorRequest, provider: LLMProvider,
                     settings: Settings, cache: JsonCache, diagnostics: Diagnostics,
                     progress: Callable[[str], None] = print,*,draft_path: Path | None = None) -> EditPlan:
    if request.style_preset and request.style_profile is None:
        from pipeline.style_profile import load_profile
        request=request.model_copy(update={"style_profile":load_profile(settings,request.style_preset)})
    if not brief.facts:
        raise DirectorError("Brief chưa có fact để viết kịch bản. Bổ sung hoặc nghiên cứu lại nguồn; không dùng tín hiệu xã hội làm fact.")
    if request.script_style is not None:
        if request.requested_duration_sec is None:
            from agents.adaptive import duration_for_brief
            request=request.model_copy(update={"requested_duration_sec":request.duration_sec,"duration_sec":duration_for_brief(brief,request.duration_sec)})
        from agents.director_story import create_story_plan
        return create_story_plan(brief,request,provider,settings,cache,diagnostics,progress,draft_path=draft_path)
    template = (settings.prompts_dir / f"director_{request.video_type}.txt").read_text(encoding="utf-8")
    common = (settings.prompts_dir / "director_common.txt").read_text(encoding="utf-8")
    from pipeline.style_profile import guidance,apply_defaults
    data = {"style_profile":guidance(request.style_profile),"discovery_hint":brief.discovery_hint.model_dump(mode="json") if brief.discovery_hint else None,"request": request.model_dump(mode="json"), "voice": settings.default_voice,
            "speech_budget":speech_budget(request.duration_sec),"research_depth":brief.research_depth,
            "story_angles":[angle.model_dump(mode="json") for angle in brief.story_angles],
            "brief_details":{field:[row.model_dump(mode="json") for row in getattr(brief,field)] for field in ("key_numbers","timeline","why_it_matters","counterpoints","glossary")},
            "content_scene_count":content_scene_count(request.duration_sec,len(brief.facts)),
            "timing_blueprint": timing_blueprint(request.duration_sec,len(brief.facts)),
            "facts": director_facts(brief),
            "trend_insights": brief.trend_insights.model_dump(mode="json"),
            "topic": brief.topic, "risks": brief.risks}
    from agents.validation_rules import groups
    inputs = {"validation_policy":groups(),"style_profile_hash":cache_key(request.style_profile.model_dump(mode="json")) if request.style_profile else None,"data": data, "brief_hash": brief_hash(brief), "model": provider.model_name,
              "prompt": cache_key([common, template]), "schema": cache_key(EditPlan.model_json_schema())}
    cached = cache.get("director-plan-v2", inputs)
    if isinstance(cached, dict):
        try:
            plan = validate_plan(EditPlan.model_validate(cached), brief, request)
            audit_plan(plan, brief, provider, settings, cache, diagnostics)
            progress("Dùng Edit Plan đã cache và kiểm tra lại.")
            return plan
        except (ValueError, ValidationError):
            pass
    prompt = common + "\n" + template + "\nINPUT_DATA_JSON:\n" + json.dumps(data, ensure_ascii=False)
    last, candidate, repair_ids = None,None,set()
    attempts = min(3,settings.retry_attempts)
    for attempt in range(1, attempts + 1):
        try:
            if candidate is not None and repair_ids:
                raw = provider.generate_json(prompt,SceneRepairs)
                repairs = SceneRepairs.model_validate(normalize_plan_structure(json.loads(raw),reference=candidate,diagnostics=diagnostics,query_provider=provider))
                replacement = {scene.id:scene.model_dump(mode="json") for scene in repairs.scenes if scene.id in repair_ids}
                if set(replacement)!=repair_ids:
                    from agents.validation_rules import RuleViolation
                    from schemas.validation import ValidationEvent
                    raise RuleViolation([ValidationEvent(rule_id="schema_basic",group=1,scene_id=i,action="error",message="Retry chưa trả đúng cảnh cần sửa.") for i in repair_ids-set(replacement)])
                candidate["scenes"] = [replacement.get(scene["id"],scene) for scene in candidate["scenes"]]
            else:
                raw = provider.generate_json(prompt, EditPlan)
                parsed = normalize_plan_structure(json.loads(raw),diagnostics=diagnostics,query_provider=provider)
                if isinstance(parsed,dict):
                    candidate = parsed
            plan = EditPlan.model_validate(candidate)
            plan.style_profile=None;plan.style_preset=None;plan.render_style=None
            if request.style_profile is not None:
                apply_defaults(plan,request.style_profile)
            fill_missing_facts(plan,brief,diagnostics)
            candidate = plan.model_dump(mode="json")
            diagnostics.record(f"Director lần {attempt}: kiểm tra cảnh {[scene.id for scene in plan.scenes]}, fact_counts={[(scene.id,len(scene.fact_ids)) for scene in plan.scenes]}, words={sum(len(scene.narration.split()) for scene in plan.scenes)}, duration={plan.duration_sec}")
            plan = validate_plan(plan, brief, request,check_title=False,diagnostics=diagnostics,allow_merge=False)
            plan.video_type = request.video_type
            plan.target_duration_sec = request.duration_sec
            plan.brief_hash = brief_hash(brief)
            candidate = plan.model_dump(mode="json")
            for scene in plan.scenes:
                for warning in scene.review_notes.warnings if scene.review_notes else []:
                    diagnostics.record(f"Director lần {attempt}, cảnh {scene.id}: {warning}")
            progress("Đang đối chiếu lời đọc và overlay với fact trong brief…")
            audit_plan(plan, brief, provider, settings, cache, diagnostics)
            validate_plan(plan,brief,request,diagnostics=diagnostics)
            # Local post-audit merging only preserves checked statements and their facts.
            audit_template=(settings.prompts_dir/"director_audit.txt").read_text(encoding="utf-8")
            audit_inputs={"data":{"facts":director_facts(brief),"plan":plan.model_dump(mode="json",exclude={"style_profile"})},"model":provider.model_name,"prompt":cache_key(audit_template)}
            cache.set("director-audit-v2",audit_inputs,{"approved":True,"issues":[]})
            cache.set("director-plan-v2", inputs, plan.model_dump(mode="json"))
            return plan
        except GeminiOutputError as error:
            diagnostics.record_exception(error, f"Director output, attempt={attempt}")
            if not error.retryable:
                last = error
                break
            last = error
        except ProviderError as error:
            diagnostics.record_exception(error,f"Director API dừng retry mù, attempt={attempt}, scenes={sorted(repair_ids)}")
            last = error
            break
        except (ValueError, ValidationError) as error:
            diagnostics.record_exception(error, f"Director schema/duration/grounding, attempt={attempt}")
            last = error
            if hasattr(error,"scene_ids") and not error.scene_ids:
                break  # A global hard error has no scene to rewrite safely.
            # Chỉ đưa feedback đã lọc, không gửi traceback, key hoặc cấu hình cho model.
            if isinstance(error, ValidationError):
                feedback = json.dumps(error.errors(include_input=False, include_context=False, include_url=False), ensure_ascii=False)
            else:
                feedback = str(error)
            if isinstance(error,(ValidationError,json.JSONDecodeError)):
                from agents.validation_rules import RuleViolation,schema_events
                structured=RuleViolation(schema_events(error,candidate))
                if not (isinstance(error,ValidationError) and error.title=="SceneRepairs" and repair_ids):
                    repair_ids=structured.scene_ids
                last=structured
            else:
                repair_ids = failing_scene_ids(error,candidate or {})
            repair_data = [{"scene":scene,"allowed_numbers":sorted(numbers(" ".join(vietnamese_fact(brief.facts[index-1]) for index in scene.get("fact_ids",[]) if type(index) is int and 1<=index<=len(brief.facts))))}
                for scene in (candidate or {}).get("scenes",[]) if scene.get("id") in repair_ids]
            diagnostics.record(f"Director lần {attempt}: cảnh lỗi={sorted(repair_ids)}, luật/giá trị={diagnostics.redact(feedback)}")
            prompt = (common+"\nRETRY: Chỉ sinh lại các cảnh lỗi dưới đây trong JSON {scenes:[...]}; giữ ID, số shot và thời lượng, không trả cảnh đã đạt. "
                "Chỉ dùng các số trong allowed_numbers của từng cảnh; không có căn cứ thì bỏ khẳng định. Lỗi: "+diagnostics.redact(feedback)+
                "\nINPUT_DATA_JSON:\n"+json.dumps({"facts":director_facts(brief),"failed_scenes":repair_data},ensure_ascii=False)) if candidate and repair_ids else common+"\n"+template+"\nINPUT_DATA_JSON:\n"+json.dumps(data,ensure_ascii=False)
            progress(f"Cảnh lỗi {sorted(repair_ids)} chưa đạt kiểm tra; lần {attempt}/{attempts}.")
    draft_path = draft_path or settings.output_dir/"edit_plan.draft.json"
    warnings = [diagnostics.redact(str(last))] if last else ["Không nhận được kế hoạch hợp lệ."]
    warnings += [warning for scene in (candidate or {}).get("scenes",[]) for warning in (scene.get("review_notes") or {}).get("warnings",[])]
    if candidate:
        candidate.update(video_type=request.video_type,target_duration_sec=request.duration_sec,brief_hash=brief_hash(brief))
    write_json(draft_path,json.loads(diagnostics.redact(json.dumps({"plan":candidate,"warnings":warnings,"failed_scene_ids":sorted(repair_ids),"validation_errors":[e.model_dump(mode="json") for e in getattr(last,"events",[])],"attempts":attempt,"status":"draft_requires_review"},ensure_ascii=False))))
    raise DirectorDraftError(f"Director chưa đạt sau {attempt} lần. Đã lưu bản nháp để sửa trong UI: {draft_path}") from last


def director_diagnostics(settings: Settings, debug: bool = False) -> Diagnostics:
    return Diagnostics(settings.logs_dir, debug=debug, filename="director_errors.log",
                       secrets=[settings.gemini_api_key.get_secret_value()])


def director_provider(settings: Settings, diagnostics: Diagnostics) -> GeminiProvider:
    # Chọn model riêng trong bộ cấu hình runtime, không thay đổi .env.
    provider = GeminiProvider(settings.model_copy(update={"gemini_model": settings.require_director_model()}))
    provider.diagnostics = diagnostics
    return provider


def run_director(brief_path: Path, settings: Settings, *, video_type: str = "review",
                 video_format: str = "tiktok", duration_sec: float = 45.0,
                 progress: Callable[[str], None] = print, debug: bool = False,
                 source_languages: list[str] | None = None, output_language: str = "vi",ai_clip_limit: int = 0,
                 script_style: str | None = "storytelling",creative_license: str = "strict",style_preset: str | None = None) -> Path:
    diagnostics = director_diagnostics(settings, debug)
    provider = None
    try:
        if not 0 <= ai_clip_limit <= settings.ai_clip_max_per_run:
            raise ValueError("Số clip AI vượt AI_CLIP_MAX_PER_RUN.")
        LanguageOptions(source_languages=source_languages if source_languages is not None else ["vi","en"],output_language=output_language)
        request = DirectorRequest(video_type=video_type, video_format=video_format, duration_sec=float(duration_sec),output_language=output_language,script_style=script_style,creative_license=creative_license,style_preset=style_preset)
        brief = ResearchBrief.model_validate(read_json(brief_path))
        if script_style is not None:
            from agents.adaptive import duration_for_brief
            effective=duration_for_brief(brief,duration_sec)
            if not effective: raise DirectorError("Brief không có fact hợp lệ; cần Research lại hoặc đổi chủ đề.")
            request=request.model_copy(update={"duration_sec":effective,"requested_duration_sec":float(duration_sec),"creative_license":creative_license})
            if effective<float(duration_sec): progress(f"dữ liệu mỏng: thời lượng yêu cầu {duration_sec:g}s, kế hoạch rút còn {effective:g}s.")
        settings.require_key("gemini")
        settings.require_director_model()
        settings.ensure_directories()
        progress("Director đang tạo kịch bản và Edit Plan…")
        provider = director_provider(settings, diagnostics)
        plan = create_edit_plan(brief, request, provider, settings,
                                JsonCache(settings.cache_dir, settings.cache_ttl_sec), diagnostics, progress,draft_path=brief_path.parent/"edit_plan.draft.json")
        fill_plan_prompts(plan,brief,provider,diagnostics,limit=ai_clip_limit)
        path = brief_path.parent / "edit_plan.json"
        write_json(path, plan.model_dump(mode="json"))
        resolve_draft(brief_path.parent)
        progress(f"Thời lượng kế hoạch: {plan.duration_sec:.1f}s / yêu cầu {duration_sec:.1f}s.")
        return path
    except Exception as error:
        diagnostics.record_exception(error, "Director failed")
        raise
    finally:
        if provider is not None:
            provider.close()


def save_edit_plan(brief_path: Path, plan_data: dict, settings: Settings) -> Path:
    """Lưu chỉnh sửa sau khi validate và đối chiếu căn cứ, không tạo audio/render."""
    diagnostics = director_diagnostics(settings)
    provider = None
    try:
        brief = ResearchBrief.model_validate(read_json(brief_path))
        plan = EditPlan.model_validate(normalize_plan_structure(plan_data,diagnostics=diagnostics))
        request = DirectorRequest(video_type=plan.video_type or "story", video_format=plan.format, duration_sec=plan.target_duration_sec or plan.duration_sec)
        validate_plan(plan, brief, request)
        provider = director_provider(settings, diagnostics)
        audit_plan(plan, brief, provider, settings, JsonCache(settings.cache_dir, settings.cache_ttl_sec), diagnostics)
        path = brief_path.parent / "edit_plan.json"
        write_json(path, plan.model_dump(mode="json"))
        resolve_draft(brief_path.parent)
        return path
    except Exception as error:
        diagnostics.record_exception(error, "Director save failed")
        raise
    finally:
        if provider is not None:
            provider.close()


def main() -> int:
    configure_console()
    logging.getLogger().setLevel(logging.CRITICAL)
    parser = argparse.ArgumentParser(description="Director → edit_plan.json (Giai đoạn 3)")
    parser.add_argument("brief_path", type=Path)
    parser.add_argument("--style-preset")
    parser.add_argument("--type", dest="video_type", choices=["news", "review", "story"], default="review")
    parser.add_argument("--format", dest="video_format", choices=["tiktok", "youtube"], default="tiktok")
    parser.add_argument("--duration", type=float, default=45.0, help="Gợi ý 30 / 60 / 90 / 120 / 180 giây; vẫn nhận thời lượng cũ")
    parser.add_argument("--style",choices=["storytelling","news","explain","review"],default="storytelling")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--source-languages",nargs="+",choices=["vi","en","zh","ko","ja"],default=["vi","en"])
    parser.add_argument("--output-language",choices=["vi"],default="vi")
    parser.add_argument("--ai-clips",type=int,default=0,help="Chuẩn bị prompt cho N shot AI; chưa gọi API tạo video")
    args = parser.parse_args()
    diagnostics = Diagnostics(Path(__file__).resolve().parents[1] / "logs", debug=args.debug, filename="director_errors.log")
    try:
        path = run_director(args.brief_path, get_settings(), video_type=args.video_type,
                            video_format=args.video_format, duration_sec=args.duration, debug=args.debug,source_languages=args.source_languages,output_language=args.output_language,ai_clip_limit=args.ai_clips,script_style=args.style,style_preset=args.style_preset)
    except Exception as error:
        diagnostics.record_exception(error, "Director CLI failed")
        print("Director chưa hoàn tất: " + diagnostics.redact(str(error))[:1500])
        print(f"Chi tiết lỗi: {diagnostics.path}")
        return 1
    print(f"Hoàn tất: {path}")
    print("Dừng ở Giai đoạn 3. Chưa tạo audio hoặc render video.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
