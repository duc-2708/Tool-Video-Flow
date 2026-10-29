import re
from typing import Optional
from dataclasses import dataclass
from enum import Enum

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
    "nit": ("nit", "Độ sáng"),
    "nits": ("nits", "Độ sáng"),
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
    scale: str
    currency: str
    unit_display: str
    formatted_number: str
    formatted_text: str
    raw_text: str
    full_numeric_value: float
    label: str = ""

def format_vi_number(val: float, max_decimals: int = 2) -> str:
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
    if not raw_text or not isinstance(raw_text, str):
        return None
    text = raw_text.strip()
    if not text:
        return None

    # Check if string is SOLELY a model identifier or name (e.g., "A20", "Chip M6", "iPhone 18", "M6")
    # without any actual metric measurement
    is_pure_model = bool(re.fullmatch(r"(?:chip|bộ xử lý|phiên bản|dòng|iphone|ipad|macbook|galaxy|snapdragon|rtx)?\s*[A-Za-z]+\d+\b", text, re.I))
    if is_pure_model:
        return None

    # 1. Phát hiện tech unit đi liền với số (e.g. "2nm", "120Hz", "1TB", "2.000 nit")
    # First, mask out model identifiers like "Chip M6", "A20" so their numbers don't confuse metric extraction
    model_pattern = r"\b(?:chip|bộ xử lý|phiên bản|dòng|iphone|ipad|macbook|galaxy|snapdragon|rtx)\s+[A-Za-z0-9_-]+|\b[A-Za-z]+\d+\b"
    cleaned_for_metric = re.sub(model_pattern, " ", text, flags=re.I).strip()

    # If nothing left or no numbers, return None
    if not re.search(r"\d", cleaned_for_metric):
        return None

    # 2. Check tech unit in cleaned_for_metric
    for unit_key, (std_unit, default_label) in TECH_UNITS_MAP.items():
        # Look for e.g. "2nm", "2 nm", "120Hz", "120 Hz", "1TB"
        m_tech = re.search(r"(\d+(?:[.,]\d+)*)\s*" + re.escape(unit_key) + r"\b", cleaned_for_metric, re.I)
        if m_tech:
            raw_num_str = m_tech.group(1)
            # Normalize number string
            norm_num = raw_num_str.replace(".", "").replace(",", ".") if ("," in raw_num_str and "." in raw_num_str) else (raw_num_str.replace(",", ".") if "," in raw_num_str and len(raw_num_str.split(",")[1]) in (1, 2) else raw_num_str.replace(".", "").replace(",", ""))
            try:
                num_val = float(norm_num)
            except ValueError:
                continue
            fmt_num = format_vi_number(num_val)
            fmt_text = f"{fmt_num} {std_unit}"
            # Extract suggested label from text if available
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

    # 3. Standard currency, percent, and scale detection
    has_percent = bool(re.search(r"%\s*|phần trăm", text, re.I))
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

    # Trích xuất số thực tế từ cleaned_for_metric
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
