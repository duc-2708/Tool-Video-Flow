with open("agents/illustrations.py", "r", encoding="utf-8") as f:
    c = f.read()

pos = c.find("def spoken_stat(text, allowed):")
assert pos != -1
end_pos = c.find("def enough(name, data):", pos)
assert end_pos != -1

new_code = '''def spoken_stat(text, allowed):
    from agents.vietnamese_tts import spoken_to_digits
    from editor.format_number import parse_display_number, NumberKind
    digits = spoken_to_digits(text)
    accepted = {str(n).rstrip('%') for n in allowed}

    # Match potential number phrases including tech units (nm, Hz, TB) and currency/scale
    display_matches = re.finditer(
        r"(?<!\\w)(\\d+(?:[.,]\\d+)*\\s*(?:[A-Za-z%€$đ]+)?)(?!\\w)",
        text,
        re.I,
    )
    candidates = []
    for m in display_matches:
        cand_text = m.group(1).strip()
        parsed = parse_display_number(cand_text)
        if not parsed:
            continue
        full_str = str(int(parsed.full_numeric_value)) if parsed.full_numeric_value.is_integer() else str(parsed.full_numeric_value)
        cand_str = str(int(parsed.value)) if parsed.value.is_integer() else str(parsed.value)
        if full_str in accepted or cand_str in accepted or any(acc in cand_text for acc in accepted):
            raw = str(int(parsed.value)) if parsed.value.is_integer() else str(parsed.value)
            if 1900 <= parsed.value <= 2100 and parsed.value.is_integer() and not parsed.scale and not parsed.currency:
                continue
            if re.search(r'(?:ngày|tháng|năm)\\s+' + re.escape(raw) + r'\\b', digits, re.I):
                continue
            # Priority score: has specific unit/currency > bare number
            has_unit = bool(parsed.unit_display)
            priority = 2 if (parsed.kind in (NumberKind.MONEY, NumberKind.PERCENT, NumberKind.TECH_METRIC) and has_unit) else (1 if has_unit else 0)
            candidates.append((priority, parsed))

    if candidates:
        # Pick highest priority, then highest absolute value
        candidates.sort(key=lambda item: (item[0], item[1].full_numeric_value), reverse=True)
        best = candidates[0][1]
        return best.value, best.unit_display, best.formatted_text

    # Dự phòng normalized_numbers
    cand_tokens = {n for n in normalized_numbers(text, ignore_current_year=False) if n.rstrip('%') in accepted}
    for token in sorted(cand_tokens, key=lambda n: ('%' not in n, -abs(float(n.rstrip('%'))))):
        value = float(token.rstrip('%'))
        if 1900 <= value <= 2100 and value.is_integer():
            continue
        raw = str(int(value)) if value.is_integer() else str(value)
        if re.search(r'(?:ngày|tháng|năm)\\s+' + re.escape(raw) + r'\\b', digits, re.I):
            continue
        parsed_token = parse_display_number(token)
        if parsed_token:
            return parsed_token.value, parsed_token.unit_display, parsed_token.formatted_text
        return value, ('%' if token.endswith('%') else ''), token
    return None

'''

c = c[:pos] + new_code + c[end_pos:]
with open("agents/illustrations.py", "w", encoding="utf-8") as f:
    f.write(c)

print("Successfully updated spoken_stat in agents/illustrations.py!")
