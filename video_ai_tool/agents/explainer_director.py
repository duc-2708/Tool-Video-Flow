"""Explainer v2 orchestrates checked outline, writing, humanization and warning critic."""
import json
import re
from pathlib import Path
from copy import deepcopy
from schemas.explainer import (ExplainerOutline,ExplainerScript,ExplainerRepairs,ScriptCritic,LoopReview)
from schemas.edit_plan import EditPlan,Scene,Shot
from agents.director_state import DirectorState
from agents.explainer_guard import sync_narration,limit_attribution,SOFT
from utils.atomic_io import write_json_atomic
from utils.cache import cache_key


def checkpoint_summary(path):
    """Only this project's script/outline, never source video's reference texts."""
    from utils.atomic_io import read_json_atomic
    data=read_json_atomic(path);result={}
    for name in ("outline","written","humanized"):
        stage=data.get("stages",{}).get(name,{})
        if stage.get("status")!="done": continue
        row=stage.get("data",{})
        result[name]={k:row[k] for k in ("hook","open_loop","payoff","title","main_points") if k in row}
        result[name]["scenes"]=[{k:s[k] for k in ("id","scene_id","narration","fact_ids","purpose") if k in s} for s in row.get("scenes",[])]
    return result


def call(provider,prompt,payload,schema,stage):
    # Do not resend the entire reference profile and three legacy scripts to
    # the small critic/repair/loop calls. Retain event facts and their source.
    payload=dict(payload)
    if stage not in {"outline","written","humanized"}:
        payload.pop("legacy_checkpoint",None)
        if "facts" in payload:
            payload["facts"]=[{k:f[k] for k in ("id","fact_vi","source_name","published_at") if k in f} for f in payload["facts"]]
        if isinstance(payload.get("style_profile"),dict):
            profile=payload["style_profile"]
            payload["style_profile"]={k:profile[k][:5] if isinstance(profile.get(k),list) else profile[k] for k in ("connective_phrases","narration_rules","shot_seconds") if k in profile}
    instructions={
        "outline":"Tạo dàn ý 5–7 beat cho 60s. Mỗi beat có một ý mới về cơ chế/nguyên nhân/ví dụ/ẩn dụ/phản biện. Không biến mỗi fact thành một beat kể tin.",
        "written":"Viết kịch bản theo dàn ý. 60s chỉ 150–180 từ TOÀN BỘ; ít nhất 60% từ là explain/opinion mềm. Chỉ dùng vài fact sự kiện quan trọng, không cố nêu hết số liệu/nguồn. Hook <=20 từ. Beat khác 24–30 từ.",
        "humanized":"Viết lại kịch bản cho giọng kể tự nhiên, giữ nhãn và căn cứ. RÚT GỌN còn 150–180 từ cho 60s, không viết thêm để dài. Phần giảng giải chiếm ít nhất 60% từ, không đọc lại dãy tin. Không nhắc tên báo vì có thẻ nguồn.",
        "script_critic":"Chấm 1–5 nghiêm khắc, KHÔNG mặc định 5. Nếu beat chỉ nêu fact mà không giải thích tại sao/như thế nào thì explanation <=2; ghi weak_scenes. Chỉ dựa vào lời đọc thực tế. Đừng nhầm metadata kind/new_information với nội dung giảng giải thật.",
        "critic_rewrite":"Trả ExplainerRepairs CHỈ các selected_scene_ids. BẮT BUỘC SỬA LẠI lời đọc các cảnh này, không chép bản cũ. Tuân thủ code_notes về giới hạn từ và kể tin. Hook 15–20 từ; beat khác 24–30 từ, tối đa 180 từ TOÀN VIDEO 60s. Giữ vài sự kiện quan trọng, bỏ số phụ; ít nhất 60% lời là cơ chế/ẩn dụ/ví dụ/phản biện có độ mềm. Không nhắc nguồn trong lời đọc vì có thẻ. Có thể đổi câu event ít quan trọng thành explain thật sự nhưng không đổi nhãn câu event cũ để lách fact.",
        "open_loop_review":"Chỉ đánh giá ngữ nghĩa question và ending. answered chỉ true nếu kết thật sự giải đáp, không coi việc lặp số/lặp câu hỏi là trả lời. Nếu không, gợi ý câu hỏi khác thực sự được ending trả lời hoặc để rỗng. Không tạo thông tin mới.",
        "replacement_loop_review":"Kiểm tra ngữ nghĩa lần cuối: ending có trả lời question không? Không thì answered=false; không viết lại kịch bản.",
        "factual_repair":"Chỉ sửa cảnh lỗi trong selected_scene_ids. Đối chiếu errors và facts, không thay cảnh đạt, không thêm số/tên/phát ngôn ngoài fact.",
        "manual_rewrite":"Chỉ viết lại selected_scene_ids theo giọng style, giữ nhãn câu và facts. Không sửa cảnh khác."}
    return schema.model_validate_json(provider.generate_json(prompt+"\nSTAGE: "+stage+"\n"+instructions.get(stage,"")+"\nINPUT_DATA_JSON:\n"+json.dumps(payload,ensure_ascii=False),schema))


def script_plan(script,outline,brief,request,settings):
    scenes=[]
    for index,row in enumerate(script.scenes):
        sentences=[s.model_copy(deep=True) for s in row.sentences]
        for sentence in sentences:
            if sentence.type in {"explain","opinion"} and not re.search(SOFT,sentence.text,re.I):
                sentence.text=("Theo mình, " if sentence.type=="opinion" else "Có thể hiểu là, ")+sentence.text[:1].lower()+sentence.text[1:]
        queries=row.shot_queries or ["person explaining concept"]
        scenes.append(Scene(id=row.scene_id,role="hook" if index==0 else "cta" if index==len(script.scenes)-1 else "body",
            narration=" ".join(s.text for s in sentences),sentences=sentences,information_kind=row.kind,new_information=row.new_information,
            fact_ids=list(dict.fromkeys(i for s in sentences if s.type=="event" for i in s.fact_ids)),
            shots=[Shot(type="stock_video",semantic_query=True,query=q,duration_sec=3.,planning_duration=True,effect="zoom_in",text_overlay=None) for q in queries],
            transition_out="fade",sfx="none",pattern_interrupt=index%2==1))
    title=script.title
    from agents.content_plan import vietnamese_title
    if not vietnamese_title(title): title="Câu chuyện phía sau "+next((f.source_name for f in brief.facts),"bản tin")
    title=title[:60].rsplit(" ",1)[0] if len(title)>60 else title
    plan=EditPlan(title=title,format=request.video_format,voice=settings.default_voice,music={"mood":"calm","volume":.08},scenes=scenes,
        content_mode="explainer_v2",content_timed=True,video_type=request.video_type,requested_duration_sec=request.requested_duration_sec or request.duration_sec,
        script_style="explain",creative_license=request.creative_license,explainer_outline=outline)
    from pipeline.style_profile import apply_defaults
    apply_defaults(plan,request.style_profile)
    limit_attribution(plan,brief)
    from agents.explainer_visuals import build_v2_shots
    build_v2_shots(plan,brief)
    return plan


def script_from_plan(plan):
    return ExplainerScript(title=plan.title,scenes=[dict(scene_id=s.id,kind=s.information_kind or "mechanism",new_information=s.new_information or s.narration,
        sentences=[p.model_dump(mode="json") for p in s.sentences],shot_queries=[q.query for q in s.shots]) for s in plan.scenes])


def quality_notes(outline,plan=None):
    from difflib import SequenceMatcher
    notes=[]
    for i,beat in enumerate(outline.beats):
        for earlier in outline.beats[:i]:
            if SequenceMatcher(None,beat.new_information.casefold(),earlier.new_information.casefold()).ratio()>.83:
                notes.append((beat.id,"Ý mới gần như lặp beat trước; cần cơ chế/ví dụ/hệ quả khác."))
    if plan:
        for scene in plan.scenes:
            if len(scene.narration.split())<8: notes.append((scene.id,"Beat quá ít nội dung để giải thích."))
            if scene.role!="hook" and not any(s.type in {"explain","opinion"} for s in scene.sentences):
                notes.append((scene.id,"Beat chỉ kể lại tin; thêm cơ chế/ví dụ/ẩn dụ/mặt trái mới, không lặp số liệu."))
        limit=round((plan.requested_duration_sec or 60)*3)
        if sum(len(s.narration.split()) for s in plan.scenes)>limit:
            budget=max(12,limit//len(plan.scenes))
            notes.extend((s.id,f"Vượt ngân sách lời đọc: rút beat còn khoảng {budget} từ, hook tối đa 20 từ; giữ ý mới và fact event quan trọng.") for s in plan.scenes if len(s.narration.split())>budget or s.role=="hook")
    return notes


def checked_script(script,outline,brief,request,settings,provider,prompt,diagnostics,payload):
    """Only factual/schema errors trigger up to two scene-specific repairs."""
    from agents.director import validate_plan
    from agents.validation_rules import RuleViolation
    candidate=script
    for attempt in range(3):
        plan=script_plan(candidate,outline,brief,request,settings)
        try:
            validate_plan(plan,brief,request,check_style=False,allow_merge=False,diagnostics=diagnostics)
            return plan
        except RuleViolation as error:
            if attempt==2: error.draft_plan=plan.model_dump(mode="json");raise
            ids=error.scene_ids
            if not ids: raise
            diagnostics.record(f"Explainer factual retry {attempt+1}; cảnh={sorted(ids)}; {error}")
            fixed=call(provider,prompt,{**payload,"selected_scene_ids":sorted(ids),"script":candidate.model_dump(mode="json"),"errors":str(error)},ExplainerRepairs,"factual_repair")
            by_id={s.scene_id:s for s in fixed.scenes if s.scene_id in ids}
            candidate=candidate.model_copy(deep=True)
            candidate.scenes=[by_id.get(s.scene_id,s) for s in candidate.scenes]
    return plan


def check_open_loop(plan,provider,prompt,diagnostics,brief=None):
    outline=plan.explainer_outline
    if not outline or not outline.open_loop: return
    answer=plan.scenes[-1].narration
    question=outline.open_loop
    payload={"question":question,"ending":answer,"instruction":"Chỉ answered=true khi đoạn kết thật sự trả lời câu hỏi; không dựa vào fact_ids. Nếu không, gợi ý một replacement_question mà chính đoạn kết trả lời, hoặc để rỗng."}
    try:
        review=call(provider,prompt,payload,LoopReview,"open_loop_review")
        if review.answered: outline.payoff=answer;return
        replacement=review.replacement_question.strip()
        if replacement:
            from agents.explainer_guard import background_issues
            if re.search(r"\d",replacement) or brief is not None and background_issues(replacement,brief): replacement=""
        if replacement:
            second=call(provider,prompt,{**payload,"question":replacement},LoopReview,"replacement_loop_review")
            if second.answered:
                # Remove the unresolved question in the hook; do not attach unrelated facts.
                for sentence in plan.scenes[0].sentences:
                    if "?" in sentence.text: sentence.text=re.sub(r"[^.!?]*\?",replacement,sentence.text,count=1);break
                else:
                    from schemas.explainer import ScriptSentence
                    plan.scenes[0].sentences.append(ScriptSentence(type="explain",text=replacement))
                outline.open_loop=replacement;outline.payoff=answer
                sync_narration(plan);plan.review_notes.append("Open loop được viết lại cho khớp câu trả lời thực tế ở kết.");return
        raise ValueError(review.reason or "Kết chưa trả lời câu hỏi mở.")
    except Exception as error:
        diagnostics.record_exception(error,"Open loop chưa có xác nhận ngữ nghĩa; bỏ câu hỏi thay vì tự gán fact")
        first=plan.scenes[0]
        for sentence in first.sentences:
            if "?" in sentence.text: sentence.text=re.sub(r"[^.!?]*\?","",sentence.text).strip()
        first.sentences=[s for s in first.sentences if s.text]
        if not first.sentences:
            from schemas.explainer import ScriptSentence
            first.sentences=[ScriptSentence(type="explain",text="Mình thử nhìn chuyện này từ cơ chế phía sau.")]
        outline.open_loop="";outline.payoff=""
        sync_narration(plan);plan.review_notes.append("Đã bỏ câu hỏi mở chưa được đoạn kết giải đáp; không tự gán fact.")


def critique(plan,brief,request,settings,provider,prompt,diagnostics,payload):
    """A warning critic may request exactly one rewrite of identified weak scenes."""
    baseline=plan.model_copy(deep=True)
    try:
        critic=call(provider,prompt,{**payload,"script":script_from_plan(plan).model_dump(mode="json"),
            "instruction":"Chấm 1–5 mức GIẢNG GIẢI thay vì liệt kê, ý mới mỗi cảnh, hook, trả lời open_loop, tự nhiên; mỗi tiêu chí <3 chỉ rõ weak_scenes và lý do cụ thể."},ScriptCritic,"script_critic")
        plan.script_critic=critic
        scores=[critic.explanation,critic.novelty,critic.hook,critic.open_loop,critic.naturalness]
        code_notes=quality_notes(plan.explainer_outline,plan)
        critic.comments.extend(f"Code · cảnh {i}: {m}" for i,m in code_notes)
        if min(scores)>=3 and not code_notes: return plan
        weak={s.scene_id for s in critic.weak_scenes if s.scene_id in {c.id for c in plan.scenes}}
        weak.update(i for i,_ in code_notes)
        if critic.hook<3: weak.add(plan.scenes[0].id)
        if critic.open_loop<3: weak.add(plan.scenes[-1].id)
        if weak:
            fixed=call(provider,prompt,{**payload,"script":script_from_plan(plan).model_dump(mode="json"),"selected_scene_ids":sorted(weak),"critic":critic.model_dump(mode="json"),"code_notes":code_notes,
                "instruction":"Một vòng sửa chất lượng, chỉ selected_scene_ids. Toàn video 150–180 từ/60s. Hook 15–20 từ; beat nội dung khoảng 24–30 từ. Ít nhất 60% lời đọc explain/opinion mềm: cơ chế, ví dụ, ẩn dụ, phản biện, ý nghĩa. Chỉ giữ vài fact event quan trọng, không cố kể hết số liệu. Mỗi beat yếu phải thêm góc GIẢI THÍCH mới thay vì lặp số/tin. Giữ dữ kiện event có căn cứ, không thêm dữ kiện công ty. Không nhắc tên báo trong lời đọc vì đã có thẻ nguồn."},ExplainerRepairs,"critic_rewrite")
            script=script_from_plan(plan);by_id={s.scene_id:s for s in fixed.scenes if s.scene_id in weak}
            script.scenes=[by_id.get(s.scene_id,s) for s in script.scenes]
            candidate=script_plan(script,plan.explainer_outline,brief,request,settings)
            from agents.director import validate_plan
            validate_plan(candidate,brief,request,check_style=False,allow_merge=False,diagnostics=diagnostics)
            # Leave every accepted scene exactly unchanged.
            existing={s.id:s for s in plan.scenes}
            candidate.scenes=[s if s.id in weak else existing[s.id] for s in candidate.scenes]
            candidate.script_critic=critic
            candidate.review_notes=list(dict.fromkeys(plan.review_notes+[f"Critic/code cảnh báo: đã sửa đúng cảnh {sorted(weak)} trong một vòng; điểm hiển thị là điểm trước sửa."]))
            return candidate
        plan.review_notes.append("Critic có điểm <3 nhưng chưa chỉ ra cảnh yếu; giữ bản đã kiểm tra và hiển thị nhận xét.")
    except Exception as error:
        diagnostics.record_exception(error,"Script critic chỉ cảnh báo; giữ bản đã kiểm tra")
        baseline.script_critic=plan.script_critic
        baseline.review_notes.append("Critic/sửa chất lượng chưa thành công; giữ bản có căn cứ, không dừng pipeline.")
        return baseline
    return plan


def rewrite_explainer(plan,brief,provider,settings,diagnostics,*,scene_id=None,style="explain"):
    from agents.director import DirectorRequest,director_facts,validate_plan
    selected={scene_id} if scene_id is not None else {s.id for s in plan.scenes}
    if not selected<={s.id for s in plan.scenes}: raise ValueError("Cảnh không tồn tại.")
    request=DirectorRequest(video_type=plan.video_type or "news",video_format=plan.format,duration_sec=max(6,plan.requested_duration_sec or plan.duration_sec),content_mode="explainer_v2")
    prompt=(settings.prompts_dir/"explainer_v2.txt").read_text(encoding="utf-8")
    payload={"facts":director_facts(brief),"knowledge_notes":[n.model_dump(mode="json") for n in brief.knowledge_notes],"style":style,"script":script_from_plan(plan).model_dump(mode="json"),"selected_scene_ids":sorted(selected)}
    result=call(provider,prompt,payload,ExplainerRepairs,"manual_rewrite")
    script=script_from_plan(plan);by_id={s.scene_id:s for s in result.scenes if s.scene_id in selected}
    script.scenes=[by_id.get(s.scene_id,s) for s in script.scenes]
    checked=checked_script(script,plan.explainer_outline,brief,request,settings,provider,prompt,diagnostics,payload)
    previous={s.id:s for s in plan.scenes}
    checked.scenes=[s if s.id in selected else previous[s.id] for s in checked.scenes]
    checked.script_critic=plan.script_critic
    check_open_loop(checked,provider,prompt,diagnostics,brief)
    return validate_plan(checked,brief,request,check_style=False,allow_merge=False,diagnostics=diagnostics)


def create_explainer_plan(brief,request,provider,settings,diagnostics,progress,*,draft_path=None):
    from agents.director import director_facts,validate_plan
    from pipeline.style_profile import guidance
    prompt=(settings.prompts_dir/"explainer_v2.txt").read_text(encoding="utf-8")
    payload={"topic":brief.topic,"facts":director_facts(brief),"knowledge_notes":[n.model_dump(mode="json") for n in brief.knowledge_notes],
        "research_questions":[q.model_dump(mode="json") for q in brief.research_questions],"duration":request.duration_sec,
        "target_words":[round(request.duration_sec*2.5),round(request.duration_sec*3)],"target_beats":[5,7] if request.duration_sec<=75 else [7,12],
        "style_profile":guidance(request.style_profile)}
    payload["writing_guidance"]="Ít nhất 60% từ là giải thích/ý kiến mềm, không cố dùng mọi fact. 60s chỉ 150–180 từ toàn video, hook 15–20 từ, mỗi beat khác 24–30 từ. Không nhắc lại nguồn trong lời đọc vì có thẻ nguồn."
    legacy_path=(draft_path or settings.output_dir/"edit_plan.draft.json").with_name("director_state.legacy.json")
    if legacy_path.is_file(): payload["legacy_checkpoint"]=checkpoint_summary(legacy_path)
    path=(draft_path or settings.output_dir/"edit_plan.draft.json").with_name("director_state.explainer_v2.json")
    state=DirectorState(path,{"mode":"explainer_v2","brief":brief.model_dump(mode="json"),"request":request.model_dump(mode="json"),"prompt":prompt,"model":provider.model_name,"style":payload["style_profile"],"legacy":payload.get("legacy_checkpoint"),"version":1},diagnostics,progress)
    stage="outline";plan=None
    try:
        progress("Explainer v2 · 1/3: dàn ý theo câu hỏi và ý mới")
        outline=state.load("outline",ExplainerOutline)
        if outline is None:
            outline=call(provider,prompt,payload,ExplainerOutline,"outline")
            valid={i for i in range(1,len(brief.facts)+1)}
            if any(i not in valid for b in outline.beats for i in b.fact_ids): raise ValueError("Outline có fact_id không tồn tại.")
            state.save("outline",outline)
        payload["outline"]=outline.model_dump(mode="json")
        progress("Explainer v2 · 2/3: câu sự kiện + giải thích có nhãn")
        stage="written";written=state.load("written",ExplainerScript)
        if written is None:
            written=call(provider,prompt,payload,ExplainerScript,"written")
            plan=checked_script(written,outline,brief,request,settings,provider,prompt,diagnostics,payload)
            written=script_from_plan(plan);state.save("written",written)
        progress("Explainer v2 · 3/3: người hóa, critic và kiểm tra câu trả lời mở")
        stage="humanized";plan=state.load("humanized",EditPlan)
        if plan is None:
            baseline=checked_script(written,outline,brief,request,settings,provider,prompt,diagnostics,payload)
            try:
                human=call(provider,prompt,{**payload,"script":written.model_dump(mode="json")},ExplainerScript,"humanized")
                plan=checked_script(human,outline,brief,request,settings,provider,prompt,diagnostics,payload)
            except Exception as error:
                diagnostics.record_exception(error,"Người hóa v2 chưa đạt; giữ bản viết đã kiểm tra")
                plan=baseline;plan.review_notes.append("Dùng bản viết lượt 2 vì người hóa chưa đạt.")
            state.save("humanized",plan)
        completed=state.load("final",EditPlan) if state.data.get("quality_version")==4 else None
        if completed is not None: return validate_plan(completed,brief,request,check_style=False,allow_merge=False,diagnostics=diagnostics)
        limit_attribution(plan,brief)
        plan.review_notes=[n for n in plan.review_notes if "scene_target" not in n]
        plan.validation_events=[e for e in plan.validation_events if e.rule_id!="scene_target"]
        plan=critique(plan,brief,request,settings,provider,prompt,diagnostics,payload)
        check_open_loop(plan,provider,prompt,diagnostics,brief)
        for sid,message in quality_notes(outline,plan): plan.review_notes.append(f"Cảnh {sid}: {message}")
        from agents.explainer_visuals import build_v2_shots
        build_v2_shots(plan,brief)
        validate_plan(plan,brief,request,check_style=False,allow_merge=False,diagnostics=diagnostics)
        state.data["quality_version"]=4
        state.save("final",plan)
        return plan
    except Exception as error:
        state.failed(stage,error)
        write_json_atomic(draft_path or path.with_name("edit_plan.draft.json"),{"status":"draft_requires_review","plan":getattr(error,"draft_plan",plan.model_dump(mode="json") if plan else None),"warnings":[diagnostics.redact(str(error))],"failed_scene_ids":list(getattr(error,"scene_ids",[])),"validation_errors":[e.model_dump(mode="json") for e in getattr(error,"events",[])]})
        raise
