import re
from pathlib import Path

target_file = Path("editor/motion/scheduler.py")
code = target_file.read_text(encoding="utf-8")

old_def = """def extract_shot_brief_and_data(text: str, scene_narration: str = \"\", is_recap: bool = False) -> dict:
    \"\"\"Extract semantic intent and factual data for an individual shot without manufactured text.\"\"\"
    from editor.format_number import parse_display_number
    from agents.presentation import card_phrase

    combined_text = (text.strip() + \" \" + scene_narration.strip()).strip()
    norm = _normalize_text(combined_text)

    # 1. Parse number (with unit/currency distinction)
    p_num = parse_display_number(text) or parse_display_number(scene_narration)"""

new_def = """def extract_shot_brief_and_data(text: str, scene_narration: str = \"\", is_recap: bool = False, spoken_text: str = \"\") -> dict:
    \"\"\"Extract semantic intent and factual data for an individual shot without manufactured text.\"\"\"
    from editor.format_number import parse_display_number
    from agents.presentation import card_phrase

    combined_text = (text.strip() + \" \" + (spoken_text or scene_narration).strip()).strip()
    norm = _normalize_text(combined_text)

    # 1. Parse number strictly from the shot's spoken audio or shot text (NEVER scene fallback)
    num_source = spoken_text.strip() if spoken_text.strip() else text.strip()
    p_num = parse_display_number(num_source) or (parse_display_number(text.strip()) if text.strip() != num_source else None)"""

assert old_def in code, "old_def not found in scheduler.py"
code = code.replace(old_def, new_def)

# Update clean_lbl selection
old_lbl = """    # 2. Extract semantic label strictly from narration
    clean_lbl = card_phrase(text, scene_narration) if text else \"\"
    norm_text = _normalize_text(text or scene_narration)
    norm_lbl = _normalize_text(clean_lbl)
    lbl_words = [w for w in norm_lbl.split() if len(w) >= 2]
    # Discard clean_lbl if it is generic, ungrounded, or manufactured
    if (
        not clean_lbl
        or not any(w in norm_text for w in lbl_words)
        or any(bad in norm_lbl for bad in [\"y chinh\", \"minh hoa\", \"chi tiet\", \"noi dung\", \"y tuong\"])
    ):
        source_pool = text or scene_narration
        clauses = split_clauses_for_shot(source_pool)
        clean_lbl = clauses[0] if clauses else source_pool"""

new_lbl = """    # 2. Extract semantic label strictly from shot text or spoken narration
    clean_lbl = \"\"
    text_clean = text.strip()
    text_words = text_clean.split()
    norm_text = _normalize_text(text_clean)
    if 2 <= len(text_words) <= 6 and not any(bad in norm_text for bad in [\"y chinh\", \"minh hoa\", \"chi tiet\", \"noi dung\", \"y tuong\", \"person explaining\"]):
        clean_lbl = text_clean
    else:
        clean_lbl = card_phrase(text, scene_narration) if text else \"\"
        norm_lbl = _normalize_text(clean_lbl)
        lbl_words = [w for w in norm_lbl.split() if len(w) >= 2]
        if (
            not clean_lbl
            or not any(w in norm_text for w in lbl_words)
            or any(bad in norm_lbl for bad in [\"y chinh\", \"minh hoa\", \"chi tiet\", \"noi dung\", \"y tuong\", \"person explaining\"])
        ):
            source_pool = spoken_text or text or scene_narration
            clauses = split_clauses_for_shot(source_pool)
            clean_lbl = clauses[0] if clauses else source_pool"""

assert old_lbl in code, "old_lbl not found in scheduler.py"
code = code.replace(old_lbl, new_lbl)

# Update loop call in schedule_shots_no_repeat
old_loop_call = """        text = sh.get(\"narration\") or sh.get(\"card_text\") or sh.get(\"text\") or \"\"
        scene_narration = sh.get(\"scene_narration\") or text
        is_recap = bool(sh.get(\"is_recap\") or idx == total_shots - 1)

        brief_info = extract_shot_brief_and_data(text, scene_narration, is_recap=is_recap)"""

new_loop_call = """        card_t = sh.get(\"card_text\") or sh.get(\"text\") or \"\"
        spk_t = sh.get(\"narration\") or \"\"
        text = card_t or spk_t
        scene_narration = sh.get(\"scene_narration\") or text
        is_recap = bool(sh.get(\"is_recap\") or idx == total_shots - 1)

        brief_info = extract_shot_brief_and_data(text, scene_narration, is_recap=is_recap, spoken_text=spk_t)"""

assert old_loop_call in code, "old_loop_call not found in scheduler.py"
code = code.replace(old_loop_call, new_loop_call)

target_file.write_text(code, encoding="utf-8")
print("scheduler.py number and label extraction updated!")
