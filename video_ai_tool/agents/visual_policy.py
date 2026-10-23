"""Sentence-scoped graphic review and persistent, explicit editorial decisions.

Director retains hard event checks. Render repairs only its in-memory copy and
writes its review beside the MP4, never into resolved plan/Assets.
"""
import hashlib
import re
from pathlib import Path
from utils.atomic_io import read_json_atomic,write_json_atomic,path_lock
from schemas.visual import Visual,VisualData


def content_type(scene,shot):
    visual=shot.visual
    if visual is None:
        if scene.sentences:
            matches=[s.type for s in scene.sentences if shot.text_overlay and shot.text_overlay.casefold() in s.text.casefold()]
            if len(set(matches))==1: return matches[0]
            if all(s.type!="event" for s in scene.sentences): return scene.sentences[0].type
        return "event"
    # A source card is provenance, not a claim made by a background sentence.
    if visual.template=="source_card": return "event"
    if visual.sentence_index and visual.sentence_index<=len(scene.sentences):
        return scene.sentences[visual.sentence_index-1].type
    if scene.sentences and visual.content_type=="event":
        # Compatibility for v2 files saved before sentence_index existed.
        text=visual.data.text or visual.data.label or shot.text_overlay or ""
        matches=[s for s in scene.sentences if text.strip() and text.casefold() in s.text.casefold()]
        if matches and len({s.type for s in matches})==1: return matches[0].type
    return visual.content_type


def background_warnings(plan,brief):
    from agents.director_numbers import normalized_numbers
    from agents.validation_rules import proper_names
    result=[]
    for scene in plan.scenes:
        for index,shot in enumerate(scene.shots,1):
            if not shot.visual or shot.visual.template=="stock" or content_type(scene,shot)=="event": continue
            data=shot.visual.data
            fields=[data.text,data.label,data.title,*data.items,*[b.label for b in data.bars]]
            text=" ".join(fields)
            if any(list(proper_names(v)) for v in fields) or text:
                result.append((scene.id,f"Shot {index}: ví dụ nền, nên kiểm tra lại ({content_type(scene,shot)}); không coi là fact sự kiện."))
            has_number=bool(normalized_numbers(text,ignore_current_year=False) or data.value is not None or data.bars)
            if has_number and not re.search(r"\b(khoảng|gần|ước|hàng chục|hàng trăm|xấp xỉ|tầm)\b",text,re.I):
                result.append((scene.id,f"Shot {index}: số liệu ví dụ nền chưa có từ ước lượng; nên làm tròn và kiểm tra lại."))
            elif has_number:
                numbers=normalized_numbers(text,ignore_current_year=False)
                unrounded=[n for n in numbers if (value:=float(n.rstrip('%')))>=100 and value%10!=0]
                if unrounded:
                    result.append((scene.id,f"Shot {index}: số liệu ví dụ nền chưa làm tròn: {unrounded}; nên kiểm tra lại."))
    return result


def ordered_label(label,narration):
    """Recover a reversed label only from an actual contiguous narration span."""
    if not label or label.casefold() in narration.casefold(): return label
    # Old extraction could append a generic label after a proper name.
    match=re.fullmatch(r"(.+?)\s+(Vụ|Vụ kiện|Công ty|Sản phẩm|Ngân hàng)",label.strip(),re.I)
    if match:
        entity,prefix=match.groups()
        original=re.search(r"\b"+re.escape(prefix)+r"\s+(?:\w+\s+){0,4}?"+re.escape(entity)+r"\b",narration,re.I)
        if original: return original[0]  # Preserve source order, including intervening words.
    return label


def repair_label_order(plan):
    repaired=[]
    for scene in plan.scenes:
        for index,shot in enumerate(scene.shots,1):
            if not shot.visual: continue
            data=shot.visual.data
            for field in ("text","label","title"):
                before=getattr(data,field);after=ordered_label(before,scene.narration)
                if after!=before:
                    setattr(data,field,after)
                    repaired.append((scene.id,f"Shot {index}: giữ thứ tự nhãn từ lời đọc: {before!r} → {after!r}."))
    return repaired


def neutral_visual(scene,shot):
    text=scene.narration.casefold()
    # These describe the subject, make no new numerical or named event claim.
    choices=[(r"dữ liệu|quyền riêng tư|analytica|thông tin cá nhân","Một vụ lộ dữ liệu lớn"),
        (r"ngân hàng|lãi|vay|tài chính","Thay đổi trong hoạt động tài chính"),
        (r"nhân sự|việc làm|lao động","Thay đổi trong công việc"),
        (r"công nghệ|phần mềm|máy|trí tuệ","Cách công nghệ tác động"),
        (r"sức khỏe|y tế|bệnh","Thông tin về sức khỏe")]
    label=next((value for pattern,value in choices if re.search(pattern,text)),"Tìm hiểu diễn biến và tác động")
    return Visual(template="text_focus",data=VisualData(text=label),content_type="explain",auto_generated=True)


def signature(scene):
    return hashlib.sha256(scene.narration.encode("utf-8")).hexdigest()


def load_decisions(project):
    path=Path(project)/"visual_decisions.json"
    return read_json_atomic(path).get("shots",{}) if path.exists() else {}


def save_decision(project,scene,shot_index,choice):
    if choice not in {"neutral","keep"}: raise ValueError("Lựa chọn đồ họa không hợp lệ.")
    path=Path(project)/"visual_decisions.json"
    with path_lock(path):
        decisions=load_decisions(project)
        decisions[f"{scene.id}:{shot_index}"]={"choice":choice,"narration_hash":signature(scene)}
        write_json_atomic(path,{"version":1,"shots":decisions})


def selected_choice(decisions,scene,index):
    item=decisions.get(f"{scene.id}:{index}",{})
    return item.get("choice") if item.get("narration_hash")==signature(scene) else None


def review_for_render(plan,brief,decisions=None):
    """Never raise for grounding: return auditable findings and local repairs."""
    from agents.visual_planner import visual_issues
    decisions=decisions or {}
    order_notes=repair_label_order(plan)
    hard=visual_issues(plan,brief) if brief else [
        (s.id,f"Shot {i}: thiếu brief.json để đối chiếu đồ họa sự kiện.")
        for s in plan.scenes for i,shot in enumerate(s.shots,1)
        if shot.visual and shot.visual.template!="stock" and content_type(s,shot)=="event"]
    warnings=background_warnings(plan,brief)
    records=[]
    for scene in plan.scenes:
        for index,shot in enumerate(scene.shots,1):
            if not shot.visual: continue
            messages=[message for sid,message in hard if sid==scene.id and message.startswith(f"Shot {index}:")]
            notes=[message for sid,message in warnings+order_notes if sid==scene.id and message.startswith(f"Shot {index}:")]
            choice=selected_choice(decisions,scene,index)
            action="unchanged"
            if choice=="neutral" or (messages and choice!="keep"):
                shot.visual=neutral_visual(scene,shot)
                # Old overlay is also visible through stock/color fallback paths.
                shot.text_overlay=shot.visual.data.text
                action="neutral"
                notes.append(f"Shot {index}: đã dùng bản trung tính; lời đọc giữ nguyên.")
            elif choice=="keep":
                action="keep"
                notes.append(f"Shot {index}: Giữ nguyên (tôi chịu trách nhiệm) — lựa chọn biên tập đã lưu.")
            if messages or notes or choice:
                records.append({"scene_id":scene.id,"shot_id":index,"content_type":content_type(scene,shot),
                    "action":action,"choice":choice,"warnings":messages+notes,"visual":shot.visual.model_dump(mode="json")})
    return records
