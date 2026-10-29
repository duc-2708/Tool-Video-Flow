import re, sys
sys.path.insert(0, ".")
from validation.grounding import normalized_numbers
from editor.format_number import parse_display_number

def extract_allowed_numbers(text):
    allowed = set(normalized_numbers(text, ignore_current_year=False))
    # Extract raw tokens
    for token in re.findall(r"\b\d+(?:[.,]\d+)*\b", text):
        clean = token.replace(".", "").replace(",", ".")
        try:
            val = float(clean)
            allowed.add(str(int(val)) if val.is_integer() else str(val))
        except ValueError:
            pass
    # Extract parsed display numbers
    for m in re.finditer(r"(?<!\w)(\d+(?:[.,]\d+)*\s*(?:[A-Za-z%€$đ]+)?)(?!\w)", text):
        p = parse_display_number(m.group(1))
        if p:
            allowed.add(str(int(p.value)) if p.value.is_integer() else str(p.value))
            allowed.add(str(int(p.full_numeric_value)) if p.full_numeric_value.is_integer() else str(p.full_numeric_value))
    return allowed

if __name__ == "__main__":
    base = "Thị trường 65 tỷ USD và 29,25 tỷ với 36,2% tăng trưởng. Chip M6 tiến trình 2nm giá 54.999.000 VND."
    print("Allowed numbers:", sorted(extract_allowed_numbers(base)))
