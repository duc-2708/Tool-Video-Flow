"""Module định dạng và phân tích số liệu chuẩn tiếng Việt cho Video AI Tool.
Đảm bảo số tiền, phần trăm, quy mô và thông số công nghệ hiển thị đúng nguyên văn kịch bản,
không in chuỗi chữ số dài (>6 chữ số), không gán nhầm đơn vị và chống bịa số.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class NumberKind(str, Enum):
    PERCENT = "percent"
    MONEY = "money"
    COUNT = "count"
    MULTIPLIER = "multiplier"
    TECH_METRIC = "tech_metric"


TECH_UNITS_MAP = {
    "nm": ("nm", "Tiến trình"),
    "nanomet": ("nm", "Tiến trình"),
    "nanômét": ("nm", "Tiến trình"),
    "hz": ("Hz", "Tần số quét"),
    "khz": ("kHz", "Tần số"),
    "mhz": ("MHz", "Tần số"),
    "ghz": ("GHz", "Xung nhịp"),
    "tb": ("TB", "Dung lượng"),
    "gb": ("GB", "Dung lượng"),
    "mb": ("MB", "Dung lượng"),
    "kb": ("KB", "Dung lượng"),
    "b": ("B", "Dung lượng"),
    "nit": ("nit", "Độ sáng đỉnh"),
    "nits": ("nits", "Độ sáng đỉnh"),
    "w": ("W", "Công suất"),
    "kw": ("kW", "Công suất"),
    "wh": ("Wh", "Năng lượng"),
    "kwh": ("kWh", "Năng lượng"),
    "mah": ("mAh", "Dung lượng pin"),
    "ah": ("Ah", "Dung lượng pin"),
    "px": ("px", "Độ phân giải"),
    "fps": ("fps", "Khung hình/giây"),
    "dpi": ("dpi", "Mật độ điểm ảnh"),
    "ppi": ("ppi", "Mật độ điểm ảnh"),
    "inch": ("inch", "Kích thước"),
    "core": ("core", "Số nhân"),
    "cores": ("cores", "Số nhân"),
    "nhân": ("nhân", "Số nhân"),
    "s": ("giây", "Thời gian"),
    "giây": ("giây", "Thời gian"),
    "phút": ("phút", "Thời gian"),
    "giờ": ("giờ", "Thời gian"),
    "ngày": ("ngày", "Thời gian"),
    "tháng": ("tháng", "Thời gian"),
    "năm": ("năm", "Thời gian"),
    "km": ("km", "Khoảng cách"),
    "m": ("m", "Khoảng cách"),
    "cm": ("cm", "Kích thước"),
    "mm": ("mm", "Độ mỏng"),
    "kg": ("kg", "Trọng lượng"),
    "g": ("g", "Trọng lượng"),
    "tấn": ("tấn", "Trọng lượng"),
}


@dataclass
class ParsedDisplayNumber:
    value: float
    kind: NumberKind
    scale: str  # "nghìn", "triệu", "tỷ", ""
    currency: str  # "USD", "VND", "EUR", "$", "đ", "đồng", ""
    unit_display: str  # "tỷ USD", "triệu đồng", "nm", "Hz", "TB", "%", v.v.
    formatted_number: str  # "65", "29,25", "10", "36,2", "2", "120"
    formatted_text: str  # "65 tỷ USD", "36,2%", "2 nm", "120 Hz", "54,99 triệu đồng"
    raw_text: str
    full_numeric_value: float  # 65_000_000_000.0
    label: str = ""  # Gợi ý nhãn cho visual card


def format_vi_number(val: float, max_decimals: int = 2) -> str:
    """Định dạng số theo quy ước tiếng Việt: dấu phẩy thập phân, dấu chấm hàng nghìn, bỏ số 0 thừa."""
    if val is None:
        return "0"
    
    val = round(val, max_decimals)
    
    if val.is_integer():
        int_part = int(val)
        return f"{int_part:,}".replace(",", ".")
    
    int_part = int(val)
    frac_part = abs(val) - abs(int_part)
    frac_str = f"{frac_part:.{max_decimals}f}".split(".")[1].rstrip("0")
    
    formatted_int = f"{int_part:,}".replace(",", ".")
    return f"{formatted_int},{frac_str}"


def parse_display_number(raw_text: str) -> Optional[ParsedDisplayNumber]:
    """Phân tích chuỗi số từ văn bản/kịch bản thành đối tượng ParsedDisplayNumber chuẩn.
    
    Hỗ trợ cả thông số công nghệ (2nm, 120Hz, 1TB), tiền tệ (54,99 triệu đồng, 65 tỷ USD),
    tỷ lệ (36,2%), và loại trừ tên model/danh từ riêng (A20, M6) không có đơn vị đo.
    """
    if not raw_text or not isinstance(raw_text, str):
        return None
    
    text = raw_text.strip()
    if not text:
        return None

    # Loại bỏ trường hợp chuỗi CHỈ là tên model hoặc định danh (proper nouns)
    # Ví dụ: "A20", "Chip A20", "M6", "Chip M6", "iPhone 18"
    is_pure_model = bool(re.fullmatch(r"(?:chip|bộ xử lý|phiên bản|dòng|iphone|ipad|macbook|galaxy|snapdragon|rtx)?\s*[A-Za-z]+\d+\b", text, re.I))
    if is_pure_model:
        return None

    # 1. Phát hiện model identifiers trong chuỗi dài để không bắt nhầm chữ số của model
    # Ví dụ: "CHIP M6 TIẾN TRÌNH 2NM" -> M6 bị che, trích xuất chính xác 2NM
    model_pattern = r"\b(?:chip|bộ xử lý|phiên bản|dòng|iphone|ipad|macbook|galaxy|snapdragon|rtx)\s+[A-Za-z0-9_-]+|\b[A-Za-z]+\d+\b"
    cleaned_for_metric = re.sub(model_pattern, " ", text, flags=re.I).strip()
    if not re.search(r"\d", cleaned_for_metric):
        return None

    # 2. Kiểm tra thông số kỹ thuật (tech units)
    for unit_key, (std_unit, default_label) in TECH_UNITS_MAP.items():
        m_tech = re.search(r"(\d+(?:[.,]\d+)*)\s*" + re.escape(unit_key) + r"\b", cleaned_for_metric, re.I)
        if m_tech:
            raw_num_str = m_tech.group(1)
            if "," in raw_num_str and "." in raw_num_str:
                norm_num = raw_num_str.replace(".", "").replace(",", ".") if raw_num_str.rfind(",") > raw_num_str.rfind(".") else raw_num_str.replace(",", "")
            elif "," in raw_num_str:
                parts = raw_num_str.split(",")
                norm_num = f"{parts[0]}.{parts[1]}" if len(parts) == 2 and len(parts[1]) in (1, 2, 3) else raw_num_str.replace(",", "")
            elif "." in raw_num_str:
                parts = raw_num_str.split(".")
                norm_num = raw_num_str if len(parts) == 2 and len(parts[1]) in (1, 2, 3) else raw_num_str.replace(".", "")
            else:
                norm_num = raw_num_str
            try:
                num_val = float(norm_num)
            except ValueError:
                continue
            fmt_num = format_vi_number(num_val)
            fmt_text = f"{fmt_num} {std_unit}"
            label = default_label
            if "tiến trình" in text.lower():
                label = "Tiến trình"
            elif "tần số" in text.lower() or "quét" in text.lower():
                label = "Tần số quét"
            elif "độ sáng" in text.lower() or "sáng" in text.lower():
                label = "Độ sáng đỉnh"
            elif "dung lượng" in text.lower() or "ssd" in text.lower():
                label = "Dung lượng SSD"
            return ParsedDisplayNumber(
                value=num_val,
                kind=NumberKind.TECH_METRIC,
                scale="",
                currency="",
                unit_display=std_unit,
                formatted_number=fmt_num,
                formatted_text=fmt_text,
                raw_text=raw_text,
                full_numeric_value=num_val,
                label=label
            )

    # 3. Phát hiện phần trăm
    has_percent = bool(re.search(r"%\s*|phần trăm", text, re.I))
    
    # 4. Phát hiện loại tiền tệ
    has_usd = bool(re.search(r"\$|\busd\b|đô la|dollar", text, re.I))
    has_vnd = bool(re.search(r"đ|\bvnd\b|\bvnđ\b|đồng", text, re.I))
    has_eur = bool(re.search(r"€|\beur\b|euro", text, re.I))
    
    currency = ""
    orig_curr_word = ""
    if has_usd:
        currency = "USD"
        orig_curr_word = "USD"
    elif has_vnd:
        currency = "VND"
        orig_curr_word = "đồng" if "đồng" in text.lower() else "VND"
    elif has_eur:
        currency = "EUR"
        orig_curr_word = "EUR"
    
    # 5. Phát hiện quy mô (scale: nghìn, triệu, tỷ)
    scale = ""
    mult = 1.0
    if re.search(r"\b(?:tỷ|tỉ|billion|b)\b", text, re.I):
        scale = "tỷ"
        mult = 1_000_000_000.0
    elif re.search(r"\b(?:triệu|million|tr|m)\b", text, re.I):
        scale = "triệu"
        mult = 1_000_000.0
    elif re.search(r"\b(?:nghìn|ngàn|thousand|k)\b", text, re.I):
        scale = "nghìn"
        mult = 1_000.0
    
    # 6. Trích xuất số thực tế
    clean = re.sub(r"[\$%€đ]|phần trăm|\busd\b|\bvnd\b|\bvnđ\b|\beur\b|đô la|đồng|tỷ|tỉ|triệu|nghìn|ngàn", " ", cleaned_for_metric, flags=re.I).strip()
    m = re.search(r"(\d+(?:[.,]\d+)*)", clean)
    if not m:
        return None
    
    num_str = m.group(1)
    if "," in num_str and "." in num_str:
        if num_str.rfind(",") > num_str.rfind("."):
            normalized_num = num_str.replace(".", "").replace(",", ".")
        else:
            normalized_num = num_str.replace(",", "")
    elif "," in num_str:
        parts = num_str.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2, 3):
            normalized_num = f"{parts[0]}.{parts[1]}"
        else:
            normalized_num = num_str.replace(",", "")
    elif "." in num_str:
        parts = num_str.split(".")
        if len(parts) == 2 and len(parts[1]) in (1, 2, 3):
            normalized_num = num_str
        else:
            normalized_num = num_str.replace(".", "")
    else:
        normalized_num = num_str
    
    try:
        val = float(normalized_num)
    except ValueError:
        return None
    
    if not scale and val >= 1_000_000_000:
        scale = "tỷ"
        val = val / 1_000_000_000.0
        mult = 1_000_000_000.0
    elif not scale and val >= 1_000_000:
        scale = "triệu"
        val = val / 1_000_000.0
        mult = 1_000_000.0
    elif not scale and val >= 1_000 and not has_percent:
        if not (1900 <= val <= 2100 and val.is_integer()):
            scale = "nghìn"
            val = val / 1_000.0
            mult = 1_000.0

    if has_percent:
        kind = NumberKind.PERCENT
    elif currency or scale in ("tỷ", "triệu") or "giá" in text.lower() or "tiền" in text.lower() or "usd" in text.lower():
        kind = NumberKind.MONEY
    elif re.search(r"lần|gấp", text, re.I):
        kind = NumberKind.MULTIPLIER
    else:
        kind = NumberKind.COUNT
    
    formatted_num = format_vi_number(val)
    unit_parts = []
    if scale:
        unit_parts.append(scale)
    if orig_curr_word:
        unit_parts.append(orig_curr_word)
    elif currency:
        unit_parts.append(currency)
    elif has_percent:
        unit_parts.append("%")
    
    if has_percent and not scale:
        unit_display = "%"
        formatted_text = f"{formatted_num}%"
    elif unit_parts:
        unit_display = " ".join(unit_parts)
        formatted_text = f"{formatted_num} {unit_display}".strip()
    else:
        unit_display = ""
        formatted_text = formatted_num
    
    full_numeric_val = val * mult
    label = "Số tiền" if kind == NumberKind.MONEY else ("Tỷ lệ" if kind == NumberKind.PERCENT else "Chỉ số")
    
    return ParsedDisplayNumber(
        value=val,
        kind=kind,
        scale=scale,
        currency=currency,
        unit_display=unit_display,
        formatted_number=formatted_num,
        formatted_text=formatted_text,
        raw_text=raw_text,
        full_numeric_value=full_numeric_val,
        label=label
    )


def format_count_up(parsed: ParsedDisplayNumber, progress: float) -> str:
    """Tính giá trị hiển thị trong quá trình count_up theo tiến độ progress (0.0 -> 1.0).
    Luôn đếm trên giá trị rút gọn và kết thúc đúng nguyên văn.
    Tuyệt đối không nhảy lùi hay trở về 0 ở cuối.
    """
    if parsed is None:
        return "0"
    
    prog = max(0.0, min(1.0, progress))
    if prog >= 0.99:
        return parsed.formatted_text
    
    current_val = parsed.value * prog
    cur_formatted = format_vi_number(current_val, max_decimals=1 if not parsed.value.is_integer() else 0)
    
    if parsed.kind == NumberKind.PERCENT:
        return f"{cur_formatted}%"
    elif parsed.unit_display:
        return f"{cur_formatted} {parsed.unit_display}"
    return cur_formatted
