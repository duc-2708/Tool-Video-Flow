"""Vietnamese accent detection, validation, and recovery utilities.
Prevents unaccented Vietnamese from entering scripts, TTS, visual plans, and renders.
"""
import re
import unicodedata
from typing import Tuple, List, Dict, Any

# Complete set of Vietnamese diacritic characters (precomposed NFC)
VI_ACCENT_CHARS = set(
    "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
    "ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ"
)

# Characteristic unaccented Vietnamese words and bigrams that indicate missing diacritics
FORBIDDEN_UNACCENTED_BIGRAMS = {
    "may moc", "khoa hoc", "mo hinh", "trieu thuc", "tuong tu", "nhu viec",
    "tham dinh", "khac khe", "kiem chung", "du lieu", "khong lo", "an giau",
    "gach xay nha", "chuyen gia", "phan tich", "thay the", "con nguoi", "tuong lai",
    "tri thuc", "co ban", "thoi gian", "he thong", "nghien cuu", "phat kien",
    "ban thao", "xac minh", "phong doan", "quy luyet", "giong nhu", "ban do",
    "rung ram", "huong di", "kiem tra", "su ket hop", "tiep can", "thay doi",
    "hoan toan", "xay nha", "tung vien", "bo loc", "lam min", "cuc bo"
}

# Common Vietnamese grammatical marker words that appear in unaccented text
COMMON_UNACCENTED_MARKERS = {
    "khong", "duoc", "nhung", "trong", "nguoi", "phai", "minh", "theo",
    "chuyen", "viec", "thay", "nhin", "chua", "luong", "de", "qua", "van",
    "thuoc", "ve", "cac", "nay", "tu", "la", "co", "the", "an", "o"
}

# Dictionary for known domain phrase restorations
KNOWN_ACCENT_REPLACEMENTS = {
    "may moc co the": "máy móc có thể",
    "may moc": "máy móc",
    "khoa hoc trong tuong lai": "khoa học trong tương lai",
    "khoa hoc": "khoa học",
    "mo hinh goi y": "mô hình gợi ý",
    "mo hinh goi": "mô hình gợi",
    "mo hinh": "mô hình",
    "tham dinh khac khe": "thẩm định khắt khe",
    "tham dinh khac": "thẩm định khắc",
    "tham dinh": "thẩm định",
    "khac khe": "khắt khe",
    "trieu thuc co ban": "tri thức cơ bản",
    "tri thuc co ban": "tri thức cơ bản",
    "tri thuc": "tri thức",
    "trieu thuc": "tri thức",
    "co ban": "cơ bản",
    "tuong tu nhu viec": "tương tự như việc",
    "nhu viec": "như việc",
    "kiem tra tung vien gach xay nha": "kiểm tra từng viên gạch xây nhà",
    "kiem tra": "kiểm tra",
    "tung vien gach": "từng viên gạch",
    "gach xay nha": "gạch xây nhà",
    "moi phat kien": "mỗi phát kiến",
    "phat kien": "phát kiến",
    "he thong tu dong": "hệ thống tự động",
    "he thong": "hệ thống",
    "tu dong": "tự động",
    "can qua bo loc": "cần qua bộ lọc",
    "bo loc": "bộ lọc",
    "giong nhu ban do": "giống như bản đồ",
    "giong nhu": "giống như",
    "ban do": "bản đồ",
    "phac thao": "phác thảo",
    "rung ram": "rừng rậm",
    "chi goi y huong di": "chỉ gợi ý hướng đi",
    "goi y": "gợi ý",
    "huong di": "hướng đi",
    "con buoc kiem chung": "còn bước kiểm chứng",
    "kiem chung": "kiểm chứng",
    "van thuoc ve con nguoi": "vẫn thuộc về con người",
    "con nguoi": "con người",
    "su ket hop nay": "sự kết hợp này",
    "su ket hop": "sự kết hợp",
    "co the thay doi hoan toan": "có thể thay đổi hoàn toàn",
    "thay doi hoan toan": "thay đổi hoàn toàn",
    "hoan toan": "hoàn toàn",
    "cach con nguoi tiep can": "cách con người tiếp cận",
    "tiep can": "tiếp cận",
    "trong thoi gian toi": "trong thời gian tới",
    "thoi gian toi": "thời gian tới",
    "thoi gian": "thời gian",
    "lieu cac mo hinh nay": "liệu các mô hình này",
    "lieu cac mo hinh": "liệu các mô hình",
    "co the thay the hoan toan": "có thể thay thế hoàn toàn",
    "thay the hoan toan": "thay thế hoàn toàn",
    "thay the": "thay thế",
    "nha khoa hoc": "nhà khoa học",
    "trong tuong lai": "trong tương lai",
    "tuong lai": "tương lai",
    "xu ly luong du lieu khong lo": "xử lý lượng dữ liệu khổng lồ",
    "xu ly": "xử lý",
    "luong du lieu": "lượng dữ liệu",
    "du lieu khong lo": "dữ liệu khổng lồ",
    "du lieu tho": "dữ liệu thô",
    "du lieu": "dữ liệu",
    "khong lo": "khổng lồ",
    "tim ra quy luyet an giau": "tìm ra quy luật ẩn giấu",
    "tim ra quy luat an giau": "tìm ra quy luật ẩn giấu",
    "quy luyet": "quy luật",
    "quy luat": "quy luật",
    "an giau": "ẩn giấu",
    "ba ket qua toan hoc moi": "ba kết quả toán học mới",
    "ket qua toan hoc moi": "kết quả toán học mới",
    "toan hoc": "toán học",
    "phong thi nghiem": "phòng thí nghiệm",
    "chung minh phong doan": "chứng minh phỏng đoán",
    "chung minh": "chứng minh",
    "phong doan": "phỏng đoán",
    "lam min cuc bo": "làm mịn cục bộ",
    "ban thao": "bản thảo",
    "chuyen gia": "chuyên gia",
    "cung tham dinh": "cùng thẩm định",
    "su ho tro tai chinh": "sự hỗ trợ tài chính",
    "tai chinh": "tài chính",
    "phan tich ket qua": "phân tích kết quả",
    "phan tich": "phân tích",
    "y tuong": "ý tưởng",
}


def count_accent_chars(text: str) -> int:
    """Return count of Vietnamese accent characters in text."""
    nfc = unicodedata.normalize("NFC", str(text or ""))
    return sum(1 for c in nfc if c in VI_ACCENT_CHARS)


def has_vietnamese_accent(text: str) -> bool:
    """True if text has at least one Vietnamese accent character."""
    return count_accent_chars(text) > 0


def is_unaccented_vietnamese(text: str) -> Tuple[bool, str]:
    """
    Detect if a string is unaccented Vietnamese.
    Returns (is_unaccented, reason).
    """
    if not text or not str(text).strip():
        return False, ""
    
    clean = unicodedata.normalize("NFC", str(text).strip())
    words = clean.split()
    lower = clean.casefold()

    # 1. Check known forbidden unaccented bigrams / phrases
    for phrase in FORBIDDEN_UNACCENTED_BIGRAMS:
        pattern = r"\b" + re.escape(phrase) + r"\b"
        if re.search(pattern, lower):
            return True, f"Chứa cụm từ tiếng Việt không dấu bị cấm: '{phrase}'"

    # 2. Check sentences with > 6 words that lack Vietnamese accents
    # We break text into sentences/clauses
    clauses = re.split(r"[.!?;\n]+", clean)
    for clause in clauses:
        c_words = [w for w in clause.strip().split() if any(ch.isalpha() for ch in w)]
        if len(c_words) > 6:
            accent_count = count_accent_chars(clause)
            if accent_count == 0:
                # Check if it has Vietnamese markers (to avoid false-flagging pure English)
                c_lower = clause.casefold()
                markers_found = [m for m in COMMON_UNACCENTED_MARKERS if re.search(r"\b" + m + r"\b", c_lower)]
                if len(markers_found) >= 2 or any(p in c_lower for p in ("mo hinh", "du lieu", "khong lo", "toan hoc", "chuyen gia")):
                    return True, f"Câu dài >6 từ không có dấu tiếng Việt ({len(c_words)} từ, chứa từ '{', '.join(markers_found[:3])}'): '{clause.strip()[:60]}...'"

    # 3. Ratio check for longer texts (> 15 words)
    if len(words) >= 15:
        total_letters = sum(1 for c in clean if c.isalpha())
        if total_letters > 0:
            ratio = count_accent_chars(clean) / total_letters
            if ratio < 0.015:
                # If ratio is under 1.5% while containing Vietnamese markers, it's unaccented
                markers = [m for m in COMMON_UNACCENTED_MARKERS if re.search(r"\b" + m + r"\b", lower)]
                if len(markers) >= 3:
                    return True, f"Tỉ lệ ký tự có dấu quá thấp ({ratio:.1%}) trên đoạn văn tiếng Việt: '{clean[:60]}...'"

    return False, ""


def restore_known_accents(text: str) -> str:
    """
    Auto-repair known unaccented Vietnamese phrases into accented counterparts.
    Preserves existing accents and proper casing.
    """
    if not text:
        return text
    
    result = str(text)
    # Sort replacements by length descending so longer phrases match first
    sorted_pairs = sorted(KNOWN_ACCENT_REPLACEMENTS.items(), key=lambda p: len(p[0]), reverse=True)
    
    for unaccented, accented in sorted_pairs:
        # Match case-insensitively with word boundaries
        pattern = re.compile(r"\b" + re.escape(unaccented) + r"\b", re.IGNORECASE)
        
        def _replace_match(match: re.Match) -> str:
            m_text = match.group(0)
            if m_text.isupper():
                return accented.upper()
            elif m_text.istitle() or (len(m_text) > 0 and m_text[0].isupper() and (len(m_text) == 1 or m_text[1].islower())):
                return accented.capitalize()
            return accented

        result = pattern.sub(_replace_match, result)
        
    return unicodedata.normalize("NFC", result)


def audit_plan_accents(plan) -> List[str]:
    """
    Audit an EditPlan object for unaccented Vietnamese text.
    Returns a list of violation messages.
    """
    violations = []
    if not plan:
        return violations

    # Check title
    if getattr(plan, "title", None):
        is_bad, reason = is_unaccented_vietnamese(plan.title)
        if is_bad:
            violations.append(f"Tiêu đề: {reason}")

    # Check each scene
    scenes = getattr(plan, "scenes", []) or []
    for sc in scenes:
        sc_id = getattr(sc, "id", None) or getattr(sc, "scene_id", None)
        narration = getattr(sc, "narration", "")
        if narration:
            is_bad, reason = is_unaccented_vietnamese(narration)
            if is_bad:
                violations.append(f"Cảnh {sc_id} (lời đọc): {reason}")

        # Sentences
        sentences = getattr(sc, "sentences", []) or []
        for s in sentences:
            s_text = getattr(s, "text", "")
            if s_text:
                is_bad, reason = is_unaccented_vietnamese(s_text)
                if is_bad:
                    violations.append(f"Cảnh {sc_id} (câu): {reason}")

        # Shots / Card texts
        shots = getattr(sc, "shots", []) or []
        for sh in shots:
            card_text = getattr(sh, "card_text", "")
            if card_text:
                is_bad, reason = is_unaccented_vietnamese(card_text)
                if is_bad:
                    violations.append(f"Cảnh {sc_id} (thẻ): {reason}")

        # Visual plan
        vp = getattr(sc, "visual_plan", None)
        if vp:
            data = getattr(vp, "data", None)
            if data:
                for fld in ("text", "label", "title"):
                    val = getattr(data, fld, None)
                    if isinstance(val, str) and val:
                        is_bad, reason = is_unaccented_vietnamese(val)
                        if is_bad:
                            violations.append(f"Cảnh {sc_id} (visual {fld}): {reason}")
                items = getattr(data, "items", []) or []
                for itm in items:
                    if isinstance(itm, str) and itm:
                        is_bad, reason = is_unaccented_vietnamese(itm)
                        if is_bad:
                            violations.append(f"Cảnh {sc_id} (visual item): {reason}")

    return violations
