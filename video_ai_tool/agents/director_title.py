"""Video-level title checks; never attribute a title error to a scene."""
from datetime import datetime
import json
import re
from agents.director_numbers import normalized_numbers
from schemas.story import VideoTitle


def title_numbers(plan,brief,*,now=None):
    now=now or datetime.now()
    numbers=lambda text:normalized_numbers(text,ignore_current_year=False)
    facts=" ".join(f.fact_vi or f.claim for f in brief.facts)
    allowed=numbers(facts)|numbers(brief.topic)|{str(now.year)}
    if brief.discovery_hint:
        allowed |= numbers(brief.discovery_hint.suggestion.topic)
    body_ids={s.id for s in plan.scenes if s.role=="body"}
    item_count=len(body_ids)
    if plan.story_outline:
        used_points={s.point_id for s in plan.story_outline.scenes if s.scene_id in body_ids}
        item_count=len(used_points)
    # Ordinal counts are positional: "Top 3" does not authorize a price of $3.
    ordinal=re.compile(r"\b(?:top\s+(\d+)|(\d+)\s+(?:điều|lý do|cách|mẹo|ý chính|bài học|điểm|mục|bí quyết|sai lầm|lưu ý|sự thật)(?!\w))",re.I)
    ordinal_used=set()
    invalid_ordinals=set()
    def strip_count(match):
        value=int(match.group(1) or match.group(2))
        if value==item_count and value>0:
            ordinal_used.add(str(value));return " "
        invalid_ordinals.add(str(value))
        return match.group(0)
    remainder=ordinal.sub(strip_count,plan.title)
    # Only a calendar reference authorizes the current month, not a price.
    remainder=re.sub(rf"\btháng\s+0?{now.month}\b"," ",remainder,flags=re.I)
    actual=numbers(remainder)
    return {"actual":actual,"allowed":allowed,"invalid":(actual-allowed)|invalid_ordinals,
        "ordinal_counts":ordinal_used,"item_count":item_count,"month":now.month}


def ensure_title(plan,brief,*,provider=None,diagnostics=None,now=None):
    def check():
        result=title_numbers(plan,brief,now=now)
        if diagnostics:
            diagnostics.record(f"Kiểm tra đối tượng=tiêu đề: số={sorted(result['actual'])}; "
                f"tập số hợp lệ={sorted(result['allowed'])}; thứ tự hợp lệ={sorted(result['ordinal_counts'])}; "
                f"số mục thực tế={result['item_count']}; tháng hiện tại={result['month']}; sai={sorted(result['invalid'])}")
        return result
    result=check()
    if not result["invalid"]: return plan
    original=plan.title
    if provider is not None:
        payload={"title":original,"topic":brief.topic,"allowed_numbers":sorted(result["allowed"]),
            "invalid_numbers":sorted(result["invalid"]),"actual_item_count":result["item_count"]}
        prompt=("Chỉ viết lại TIÊU ĐỀ tiếng Việt trong JSON {title:...}; không viết lại cảnh/kịch bản. "
            "Chỉ dùng số trong allowed_numbers; Top N/N điều phải khớp actual_item_count. "
            "Không có bằng chứng thì bỏ con số, không thêm khẳng định.\nINPUT_DATA_JSON:\n"+json.dumps(payload,ensure_ascii=False))
        try:
            plan.title=VideoTitle.model_validate_json(provider.generate_json(prompt,VideoTitle)).title
            result=check()
        except Exception as error:
            if diagnostics: diagnostics.record_exception(error,"Sửa riêng tiêu đề một lần thất bại; dùng chủ đề")
    if result["invalid"]:
        plan.title=brief.topic
        if check()["invalid"]:
            plan.title=" ".join(re.sub(r"\d+(?:[.,]\d+)*%?","",brief.topic).split()) or "Thông tin từ nguồn"
            check()
        message=f"Tiêu đề có số ngoài căn cứ; đã dùng chủ đề làm tiêu đề dự phòng (số không hợp lệ: {sorted(result['invalid'])})."
    else:
        message="Tiêu đề có số ngoài căn cứ; đã viết lại riêng tiêu đề một lần, giữ nguyên các cảnh."
    if message not in plan.review_notes: plan.review_notes.append(message)
    if diagnostics: diagnostics.record("Đối tượng=tiêu đề: "+message)
    return plan
