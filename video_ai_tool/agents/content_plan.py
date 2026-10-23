"""Final presentation pass: no new claims, no network, timings follow narration."""
import math
import re
from agents.broll_queries import sanitize_broll_query,unique_query,keywords
from schemas.edit_plan import Shot


def scene_seconds(scene):
    return max(len(scene.narration.split())/2.6+.8,2.5)


def fit_content_timing(plan):
    if getattr(plan,"content_mode",None)=="explainer_v2":
        # The v2 planner fits 2.5–4s shots to sentence ideas without a four-shot cap.
        return plan
    mean=plan.style_profile.shot_seconds.mean if plan.style_profile else 3.
    for scene in plan.scenes:
        duration=scene_seconds(scene)
        count=min(4,max(1,round(duration/mean)))
        pool=scene.shots
        scene.shots=[Shot.model_validate({**pool[i%len(pool)].model_dump(mode="json"),
            "planning_duration":True,"duration_sec":duration/count}) for i in range(count)]
    requested=plan.requested_duration_sec or plan.target_duration_sec or plan.duration_sec
    plan.requested_duration_sec=requested
    plan.target_duration_sec=plan.duration_sec
    if plan.duration_sec<requested*.8:
        message=f"Yêu cầu {requested:g}s, thực tế ~{plan.duration_sec:.1f}s vì dữ liệu mỏng; tăng số nguồn hoặc chọn chủ đề khác."
        if message not in plan.review_notes: plan.review_notes.append(message)
    return plan


def vietnamese_title(title):
    return bool(re.search(r"[àáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]",title,re.I)
        or re.search(r"\b(?:cua|va|tai|trong|nguoi|thong tin|cong nghe|ra mat|vi sao|cach)\b",title,re.I))


def finalize_content_plan(plan,brief,*,ai_clip_limit=0,diagnostics=None):
    """Facts and narration stay byte-for-byte; only presentation data changes."""
    plan.content_timed=True
    plan.ai_clip_limit=ai_clip_limit
    if getattr(plan,"content_mode",None)=="explainer_v2":
        from agents.explainer_visuals import build_v2_shots
        build_v2_shots(plan,brief)
        if plan.duration_sec<(plan.requested_duration_sec or plan.duration_sec)*.8:
            note="Dữ liệu sự kiện và kiến thức nền chưa đủ: giảm thời lượng thực tế; tăng nguồn hoặc chọn chủ đề khác."
            if note not in plan.review_notes: plan.review_notes.append(note)
        return plan
    if not vietnamese_title(plan.title):
        plan.title=brief.topic if vietnamese_title(brief.topic) else "Thông tin về "+brief.topic
        plan.review_notes.append("Tiêu đề được chuyển về chủ đề tiếng Việt; giữ nguyên lời đọc và fact_ids.")
    used=set()
    fit_content_timing(plan)
    for scene in plan.scenes:
        context=scene.narration+" "+" ".join(brief.facts[i-1].fact_vi or brief.facts[i-1].claim for i in scene.fact_ids if 1<=i<=len(brief.facts))
        context+=" "+brief.topic+" "+((plan.style_profile.category_id or "").replace("-"," ") if plan.style_profile else "")
        anchors=keywords(context)
        for index,shot in enumerate(scene.shots,1):
            old=shot.query
            query=sanitize_broll_query(old,context)
            generic=query in {"technology abstract","news studio","globe network","city skyline"}
            if len(anchors.split())>=2 and (generic or not set(query.split()).intersection(anchors.split())): query=anchors
            shot.query=unique_query(query,context,used);used.add(shot.query)
            if shot.query!=old:
                note=f"Cảnh {scene.id}, shot {index}: b-roll {old!r} → {shot.query!r} từ nội dung cảnh/fact."
                if diagnostics: diagnostics.record(note)
                if scene.review_notes: scene.review_notes.warnings.append(note)
            if shot.type=="ai_video" and not ai_clip_limit:
                shot.type="stock_video"
                plan.review_notes.append(f"Cảnh {scene.id}, shot {index}: clip AI tắt, dùng stock_video theo query của shot.")
    plan.review_notes=list(dict.fromkeys(plan.review_notes))
    from agents.visual_planner import assign_visuals
    assign_visuals(plan,brief)
    return plan


def draft_presentation(data,brief,request,diagnostics=None):
    """A blocked factual audit still gets readable, correctly timed draft output."""
    if not isinstance(data,dict): return data
    from schemas.edit_plan import EditPlan
    from pydantic import ValidationError
    try:
        plan=EditPlan.model_validate(data)
        plan.requested_duration_sec=request.requested_duration_sec or request.duration_sec
        if request.style_profile is not None: plan.style_profile=request.style_profile
        return finalize_content_plan(plan,brief,ai_clip_limit=getattr(request,"ai_clip_limit",0),diagnostics=diagnostics).model_dump(mode="json")
    except (ValidationError,ValueError) as error:
        if diagnostics: diagnostics.record_exception(error,"Draft chưa có schema cơ bản; giữ JSON gốc để sửa tay")
        return data
