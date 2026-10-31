from pathlib import Path

target_file = Path("editor/motion/scheduler.py")
code = target_file.read_text(encoding="utf-8")

old_code = """    # 3. Determine semantic intent & domain match
    intent = "concept"
    if is_recap:
        intent = "recap"
    elif has_number:
        intent = "number" """

old_code2 = """    # 3. Determine semantic intent & domain match
    intent = "concept"
    if is_recap:
        intent = "recap"
    elif has_number:
        intent = "number" """

code = code.replace(
"""    # 3. Determine semantic intent & domain match
    intent = "concept"
    if is_recap:
        intent = "recap"
    elif has_number:
        intent = "number" """.strip(),
"""    # 3. Determine semantic intent & domain match
    intent = "concept"
    if has_number:
        intent = "number"
    elif is_recap:
        intent = "recap" """.strip()
)

target_file.write_text(code, encoding="utf-8")
print("scheduler.py intent order updated!")
