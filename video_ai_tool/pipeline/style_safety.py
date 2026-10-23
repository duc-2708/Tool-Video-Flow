"""Only reusable delivery patterns may leave the local reference library."""
import re
from agents.vietnamese_tts import spoken_to_digits

# Common stylistic headings and sentence openings are not entities.
ORDINARY=set("Mở Giữ Cắt Dùng Kết Chuyển Nối Viết Tạo Đặt Thêm Bỏ Tránh Chỉ Chọn Lấy Đưa Xen Tăng Giảm Nhấn Chữ Nền Nhạc Câu Mỗi Ngắn Dài Nhanh Chậm Không Có Một Hai Ba Theo Nhưng Chưa Rồi Thậm Thay Đầu Sau Cuối Hãy Bạn Mình Người Phần Bối Nội Dung Khuôn Cảm Mức Xưng Lời Hình Hiệu Âm Tốc Nhịp Thân Hào Hứng Trực Tuyến Toàn Kéo Tóm Hook Body Ending Climax Opening Context Intro CTA B SFX TTS AI UI CAD API FPS GPU CPU VND USD RGB Arial Bold TikTok YouTube".split())
IDENTIFIER=r"[^\W\d_][\w’'-]*"
ORDINARY.update("Quy Cụm Giới Thiệu Thông Điều Hạ Gần Nhẹ Tò Gợi Triển Khai So Sánh Tỷ Lệ Dọc Đậm Màu Trắng Đen Vàng Xanh Đỏ".split())


def entities(text):
    # Kept for old callers: sentence capitalization is NOT entity recognition.
    return set()


COMMON=set(w.casefold() for w in ORDINARY)|set("giải thích sử dụng phân tích đánh giá cao trào chia nhỏ ví dụ hài hước nhẹ thấp vừa phải nhiều video cài giao bí tóm bắt đầu nhiệm vụ kết luận".split())
BROKEN=re.compile(r"\{topic\}\s+(?:thích|dụ|dụng|tích|giá|trào|nhỏ|hỉnh)\b",re.I)


def allowed_entities(names):
    return {name.strip() for name in names if isinstance(name,str) and name.strip()
        and name.strip().casefold() not in COMMON and "{" not in name
        and not set(re.findall(r"\w+",name.casefold())).issubset(COMMON)
        and any(c.isalpha() for c in name)
        and (len(name.split())>1 or name.isascii())}


def template_text(text,names=(),warnings=None):
    original=text
    slots={}
    def protect(match):
        token="SLOTSAFE"+chr(65+len(slots)//26)+chr(65+len(slots)%26)
        slots[token]=match[0];return token
    text=re.sub(r"\{[a-z_]+\}",protect,text)
    # Attribution/channel identities must become empty source slots, even if
    # the observed channel is written in lowercase or uses numeric branding.
    text=re.sub(r"(^|(?<=[.!?])\s+)(?:Theo|theo)\s+[A-ZÀ-Ỹ][^,;.!?\n]+(?=[,;.!?\n]|$)",r"\1Theo {source}",text)
    for name in sorted(allowed_entities(names),key=len,reverse=True):
        if not name.startswith("SLOTSAFE"):
            text=re.sub(r"(?<!\w)"+re.escape(name)+r"(?!\w)","{topic}",text,flags=re.I)
    text=spoken_to_digits(text)
    # Single spoken cardinals before factual units must also become slots;
    # retain structural rules such as 'mỗi cảnh một ý'.
    text=re.sub(r"\b(?:không|một|hai|ba|bốn|tư|năm|sáu|bảy|tám|chín|mười)\b(?=\s+(?:ngày|tuần|tháng|năm|giờ|tiếng|phút|giây|triệu|tỷ|đô|đồng|sản phẩm|bức ảnh)\b)","{number}",text,flags=re.I)
    text=re.sub(r"\d+(?:[.,:/-]\d+)*(?:\s*%|[A-Za-z]+)?","{number}",text)
    for token,value in slots.items(): text=text.replace(token.casefold(),value).replace(token,value)
    if BROKEN.search(text) or any(len(re.findall(r"\{\w+\}",sentence))>2 for sentence in re.split(r"[.!?]",text)):
        # Safe fallback is derived from the original, never from a broken template.
        safe=original
        safe=re.sub(r"(^|(?<=[.!?])\s+)(?:Theo|theo)\s+[A-ZÀ-Ỹ][^,;.!?\n]+(?=[,;.!?\n]|$)",r"\1Theo {source}",safe)
        for name in sorted(allowed_entities(names),key=len,reverse=True):
            safe=re.sub(r"(?<!\w)"+re.escape(name)+r"(?!\w)","",safe,flags=re.I)
        safe=re.sub(r"\d+(?:[.,:/-]\d+)*(?:\s*%|[A-Za-z]+)?","",spoken_to_digits(safe))
        if BROKEN.search(safe): safe="Triển khai nội dung theo dữ kiện"
        if warnings is not None: warnings.append("Hồ sơ: phát hiện placeholder làm hỏng câu/quá 2 placeholder; dùng bản gốc đã bỏ tên riêng và số liệu.")
        text=" ".join(safe.split())
    return text.strip()


def sanitize_profile(profile):
    """Keep raw reference_texts for local anti-copy checks; never send them."""
    profile=profile.model_copy(deep=True)
    names=allowed_entities(profile.reference_entities)
    clean=lambda value:template_text(value,names,profile.warnings)
    lists=("hook_templates","hook_techniques","narration_rules","broll_patterns","visual_effects","transitions","ending_techniques","reusable_rules","narrative_flows","connective_phrases")
    for field in lists: setattr(profile,field,list(dict.fromkeys(clean(t) for t in getattr(profile,field))))
    for row in profile.structure: row.name=clean(row.name)
    for row in profile.rule_frequencies+profile.connective_frequencies: row.rule=clean(row.rule)
    for row in profile.scene_patterns:
        row.purpose=clean(row.purpose);row.transition=clean(row.transition);row.connective_template=clean(row.connective_template)
        for field in ("visual_types","effects","overlay_styles","sfx"): setattr(row,field,[clean(t) for t in getattr(row,field)])
    for field in ("font_description","emphasis","shadow"): setattr(profile.captions,field,clean(getattr(profile.captions,field)))
    profile.audio.details=clean(profile.audio.details);profile.audio.mood=clean(profile.audio.mood)
    profile.audio.sfx_types=[clean(t) for t in profile.audio.sfx_types]
    profile.warnings=list(dict.fromkeys(profile.warnings))
    return profile
