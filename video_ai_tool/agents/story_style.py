"""Code checks for new story plans; legacy plans keep their original contract."""
import math
import re
from collections import Counter
from config.storytelling import DURATIONS

CLICHES = ("một số", "nhiều người", "ngày càng", "đóng vai trò quan trọng", "không thể phủ nhận", "trong bối cảnh", "có thể nói rằng")
HOOK_BANNED = ("chào mọi người", "hôm nay chúng ta sẽ", "trong thời đại ngày nay")
CONNECTORS = ("nhưng khoan đã", "vấn đề là", "thử tưởng tượng")


def data_advice(brief, duration):
    from agents.adaptive import duration_for_brief
    count = len(brief.facts)
    suggested = duration_for_brief(brief,duration)
    thin = count<8 or suggested<duration
    return {"thin":thin,"suggested_duration":suggested,
        "warning":"dữ liệu mỏng, nên tăng số nguồn hoặc giảm thời lượng" if thin else ""}


def story_blueprint(duration, fact_count, profile=None):
    if profile is not None and profile.scene_pacing:
        from pipeline.category_style import profile_blueprint
        return profile_blueprint(duration,fact_count,profile)
    from agents.adaptive import content_count
    # With one fact, merge opening/closing roles into two content-bearing scenes.
    total=2 if fact_count==1 or duration<7.5 else content_count(duration,fact_count)+2
    shot_seconds = 3.
    if profile is not None:
        shot_seconds = min(4., max(1.5, profile.shot_seconds.mean))
        proposed = max(len(profile.structure), round(duration / (shot_seconds * 2)))
        total = min(max(2, proposed), max(2, fact_count * 2), max(2, int(duration/3)))
    end = min(8,max(1.5,duration*.07))
    body_duration = (duration-3-end)/(total-2) if total>2 else 0
    rows = []
    for ordinal in range(total):
        length = min(3,duration/2) if ordinal==0 else duration-min(3,duration/2) if total==2 else end if ordinal==total-1 else body_duration
        count = max(1,math.ceil(length/shot_seconds))
        count = min(max(count, math.ceil(length/4)), max(1, math.floor(length/1.5)))
        shots = [length/count]*count
        shots[-1] = length-sum(shots[:-1])
        rows.append({"id":ordinal+1,"role":"hook" if ordinal==0 else "cta" if ordinal==total-1 else "body",
            "shot_durations_sec":shots,"pattern_interrupt":ordinal>0 and ordinal%2==0})
        if profile is not None and profile.structure:
            midpoint = (sum(sum(r["shot_durations_sec"]) for r in rows[:-1]) + length/2) / duration
            cumulative = 0.
            for section in profile.structure:
                cumulative += section.fraction
                if midpoint <= cumulative + 1e-8:
                    rows[-1]["style_section"] = section.name
                    break
    return rows


def style_issues(plan):
    errors = {}
    def add(scene, message): errors.setdefault(scene.id,[]).append(message)
    def timing_issue(scene,message): add(scene,message)
    count = sum(len(s.narration.split()) for s in plan.scenes)
    target = plan.target_duration_sec or plan.duration_sec
    speed=min(3.5,max(1.5,plan.style_profile.speech_words_per_sec.mean)) if plan.style_profile else 2.6
    if not math.ceil(target*speed*.8)<=count<=math.floor(target*speed*1.2):
        message=f"Tổng {count} từ; mục tiêu {target*speed:.0f} ±20%, chỉ thêm chi tiết có fact."
        for scene in plan.scenes[1:]: timing_issue(scene,message)
    last_opening = None
    connectors = Counter()
    seen = set()
    for i,scene in enumerate(plan.scenes):
        text = scene.narration
        lower = text.casefold()
        if not scene.fact_ids and scene.role!="cta": add(scene,"Mỗi cảnh cần fact_ids hợp lệ, kể cả kết nối lại câu hỏi đầu video.")
        for phrase in CLICHES:
            if phrase in lower: add(scene,"Cụm sáo rỗng bị cấm: "+phrase)
        if i==0:
            if len(text.split())>min(20,math.ceil(scene.duration_sec*2.8)): add(scene,"Hook quá dài cho ba giây đầu.")
            if any(phrase in lower for phrase in HOOK_BANNED): add(scene,"Hook dùng cách mở đầu bị cấm.")
            if "?" not in text and not re.search(r"\d|phần trăm|triệu|tỷ|nhưng|lại",lower): add(scene,"Hook cần câu hỏi, con số hoặc mâu thuẫn có căn cứ.")
        if i>0 and not math.floor(scene.duration_sec*2.4*.9)<=len(text.split())<=math.ceil(scene.duration_sec*2.8*1.1):
            timing_issue(scene,"Lượng chữ của cảnh lệch thời lượng; phân bổ lại bằng chi tiết từ fact, không lặp ý.")
        sentences = [s for s in re.split(r"(?<=[.!?])\s+",text) if s.strip()]
        if i>0 and not 2<=len(sentences)<=4: timing_issue(scene,"Cảnh cần 2–4 câu, ý chính rồi chi tiết và câu dẫn.")
        if any(len(sentence.split())>28 for sentence in sentences): add(scene,"Câu quá 28 từ; tách tại ranh giới ý.")
        if re.search(r"[()]",text): add(scene,"Tránh ngoặc trong lời đọc; bước Assets sẽ chuyển số/đơn vị sang dạng TTS.")
        extra=tuple(p.split("{topic}")[0].strip(" .,:!?…").casefold() for p in plan.style_profile.connective_phrases) if plan.style_profile else ()
        for phrase in dict.fromkeys((*CONNECTORS,*extra)):
            if not phrase or len(phrase.split())<2:
                continue
            connectors[phrase] += lower.count(phrase)
            if connectors[phrase]>2: add(scene,"Lạm dụng chuyển ý: "+phrase)
        # Ignore compulsory attribution when comparing openings.
        body = re.sub(r"^theo [^,]+,\s*","",lower)
        opening = " ".join(body.split()[:2])
        if opening == last_opening: add(scene,"Hai cảnh liên tiếp mở bằng cùng cấu trúc.")
        last_opening = opening
        identity = " ".join(body.split()).strip(".!?")
        if identity in seen: add(scene,"Lặp nguyên ý/lời cảnh khác; giảm thời lượng hoặc thêm fact thật.")
        seen.add(identity)
        if i==len(plan.scenes)-1 and ("cảm ơn đã xem" in lower or re.search(r"\b(tóm lại|tổng kết lại|như vậy)\b",lower)):
            add(scene,"Kết bằng nhận định/câu hỏi, không tóm bài hoặc cảm ơn đã xem.")
        for shot in scene.shots:
            if shot.text_overlay:
                if not 2<=len(shot.text_overlay.split())<=5 or shot.text_overlay.casefold().strip(".!?") in {s.casefold().strip(".!?") for s in sentences}:
                    add(scene,"Overlay phải 2–5 từ/số, không lặp nguyên câu lời đọc.")
        if i>=3 and not any(s.pattern_interrupt for s in plan.scenes[i-2:i+1]):
            add(scene,"Cần pattern interrupt mỗi 2–3 cảnh.")
    return errors
