"""Module định dạng và phân tích số liệu chuẩn tiếng Việt cho Video AI Tool.
Đảm bảo số tiền, phần trăm và quy mô hiển thị đúng nguyên văn kịch bản,
không in chuỗi chữ số dài (>6 chữ số) và không gán nhầm đơn vị.
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


@dataclass
class ParsedDisplayNumber:
    value: float
    kind: NumberKind
    scale: str  # "nghìn", "triệu", "tỷ", ""
    currency: str  # "USD", "VND", "EUR", "$", "đ", ""
    unit_display: str  # "tỷ USD", "tỷ", "%", "USD", v.v.
    formatted_number: str  # "65", "29,25", "10", "36,2"
    formatted_text: str  # "65 tỷ USD", "36,2%"
    raw_text: str
    full_numeric_value: float  # 65_000_000_000.0


def format_vi_number(val: float, max_decimals: int = 2) -> str:
    """Định dạng số theo quy ước tiếng Việt: dấu phẩy thập phân, dấu chấm hàng nghìn, bỏ số 0 thừa."""
    if val is None:
        return "0"
    
    # Làm tròn theo max_decimals
    val = round(val, max_decimals)
    
    # Kiểm tra xem có phần thập phân không
    if val.is_integer():
        int_part = int(val)
        # Định dạng dấu chấm hàng nghìn
        return f"{int_part:,}".replace(",", ".")
    
    # Có phần thập phân
    int_part = int(val)
    frac_part = abs(val) - abs(int_part)
    frac_str = f"{frac_part:.{max_decimals}f}".split(".")[1].rstrip("0")
    
    formatted_int = f"{int_part:,}".replace(",", ".")
    return f"{formatted_int},{frac_str}"


def parse_display_number(raw_text: str) -> Optional[ParsedDisplayNumber]:
    """Phân tích chuỗi số từ văn bản/kịch bản thành đối tượng ParsedDisplayNumber chuẩn.
    
    Ví dụ:
        "65 tỷ USD" -> value=65.0, kind=MONEY, scale="tỷ", currency="USD", formatted_text="65 tỷ USD"
        "29,25 tỷ" -> value=29.25, kind=MONEY, scale="tỷ", currency="", formatted_text="29,25 tỷ"
        "10 tỷ USD" -> value=10.0, kind=MONEY, scale="tỷ", currency="USD", formatted_text="10 tỷ USD"
        "36,2%" -> value=36.2, kind=PERCENT, scale="", currency="", formatted_text="36,2%"
        "5,95%" -> value=5.95, kind=PERCENT, scale="", currency="", formatted_text="5,95%"
        "60 USD" -> value=60.0, kind=MONEY, scale="", currency="USD", formatted_text="60 USD"
    """
    if not raw_text or not isinstance(raw_text, str):
        return None
    
    text = raw_text.strip()
    if not text:
        return None
    
    # 1. Phát hiện phần trăm
    has_percent = bool(re.search(r"%\s*|phần trăm", text, re.I))
    
    # 2. Phát hiện loại tiền tệ
    has_usd = bool(re.search(r"\$|\busd\b|đô la|dollar", text, re.I))
    has_vnd = bool(re.search(r"đ|\bvnd\b|\bvnđ\b|đồng", text, re.I))
    has_eur = bool(re.search(r"€|\beur\b|euro", text, re.I))
    
    currency = ""
    if has_usd:
        currency = "USD"
    elif has_vnd:
        currency = "VND"
    elif has_eur:
        currency = "EUR"
    
    # 3. Phát hiện quy mô (scale: nghìn, triệu, tỷ)
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
    
    # 4. Trích xuất số thực tế
    # Hỗ trợ số như: 65, 29,25, 29.25, 10, 36,2, 5.95, 65.000.000.000
    # Chuẩn hóa tạm thời để trích xuất số
    clean = re.sub(r"[\$%€đ]|phần trăm|\busd\b|\bvnd\b|\bvnđ\b|\beur\b|đô la|đồng|tỷ|tỉ|triệu|nghìn|ngàn", " ", text, flags=re.I)
    clean = clean.strip()
    
    # Tìm chuỗi số
    m = re.search(r"(\d+(?:[.,]\d+)*)", clean)
    if not m:
        return None
    
    num_str = m.group(1)
    
    # Xử lý dấu phân cách
    if "," in num_str and "." in num_str:
        # Ví dụ 1.000,50 hoặc 1,000.50
        if num_str.rfind(",") > num_str.rfind("."):
            # Dấu phẩy là thập phân
            normalized_num = num_str.replace(".", "").replace(",", ".")
        else:
            # Dấu chấm là thập phân
            normalized_num = num_str.replace(",", "")
    elif "," in num_str:
        parts = num_str.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2, 3):
            # Thập phân tiếng Việt (e.g. 29,25 hoặc 5,95)
            normalized_num = f"{parts[0]}.{parts[1]}"
        else:
            # Phân tách hàng nghìn (e.g. 1,000,000)
            normalized_num = num_str.replace(",", "")
    elif "." in num_str:
        parts = num_str.split(".")
        if len(parts) == 2 and len(parts[1]) in (1, 2, 3):
            # Thập phân tiếng Anh (e.g. 29.25 hoặc 5.95)
            normalized_num = num_str
        else:
            # Dấu chấm hàng nghìn tiếng Việt (e.g. 65.000.000.000)
            normalized_num = num_str.replace(".", "")
    else:
        normalized_num = num_str
    
    try:
        val = float(normalized_num)
    except ValueError:
        return None
    
    # 5. Xử lý trường hợp số đầy đủ lớn (ví dụ 65000000000) khi không có scale tường minh
    if not scale and val >= 1_000_000_000:
        scale = "tỷ"
        val = val / 1_000_000_000.0
        mult = 1_000_000_000.0
    elif not scale and val >= 1_000_000:
        scale = "triệu"
        val = val / 1_000_000.0
        mult = 1_000_000.0
    elif not scale and val >= 1_000 and not has_percent:
        # Chỉ rút gọn nghìn nếu không phải phần trăm hay năm (1900-2100)
        if not (1900 <= val <= 2100 and val.is_integer()):
            scale = "nghìn"
            val = val / 1_000.0
            mult = 1_000.0

    # 6. Xác định Kind
    if has_percent:
        kind = NumberKind.PERCENT
    elif currency or scale in ("tỷ", "triệu") or "giá" in text.lower() or "tiền" in text.lower() or "usd" in text.lower():
        kind = NumberKind.MONEY
    elif re.search(r"lần|gấp", text, re.I):
        kind = NumberKind.MULTIPLIER
    else:
        kind = NumberKind.COUNT
    
    # 7. Xây dựng unit_display và formatted_text
    formatted_num = format_vi_number(val)
    
    unit_parts = []
    if scale:
        unit_parts.append(scale)
    if currency:
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
    
    return ParsedDisplayNumber(
        value=val,
        kind=kind,
        scale=scale,
        currency=currency,
        unit_display=unit_display,
        formatted_number=formatted_num,
        formatted_text=formatted_text,
        raw_text=raw_text,
        full_numeric_value=full_numeric_val
    )


def format_count_up(parsed: ParsedDisplayNumber, progress: float) -> str:
    """Tính giá trị hiển thị trong quá trình count_up theo tiến độ progress (0.0 -> 1.0).
    Luôn đếm trên giá trị rút gọn và kết thúc đúng nguyên văn.
    """
    if parsed is None:
        return "0"
    
    prog = max(0.0, min(1.0, progress))
    current_val = parsed.value * prog
    
    # Ở giai đoạn cuối (prog >= 0.99), trả về đúng chuỗi đã định dạng
    if prog >= 0.99:
        return parsed.formatted_text
    
    cur_formatted = format_vi_number(current_val, max_decimals=1 if not parsed.value.is_integer() else 0)
    
    if parsed.kind == NumberKind.PERCENT:
        return f"{cur_formatted}%"
    elif parsed.unit_display:
        return f"{cur_formatted} {parsed.unit_display}"
    return cur_formatted
