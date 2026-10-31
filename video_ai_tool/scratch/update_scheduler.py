import re
from pathlib import Path

target_file = Path("editor/motion/scheduler.py")
code = target_file.read_text(encoding="utf-8")

old_tail = """    words_lbl = clean_lbl.split()
    if len(words_lbl) > 4:
        words_lbl = words_lbl[:4]
    INCOMPLETE_TAIL = {'thiết', 'ngân', 'của', 'và', 'với', 'trong', 'từ', 'là', 'để', 'cho', 'nỗ', 'kẻ', 'các', 'những', 'một'}
    while len(words_lbl) >= 2 and words_lbl[-1].lower() in INCOMPLETE_TAIL:
        words_lbl.pop()
    # If the remaining words don't form a meaningful concept (>=2 words), drop the label completely
    clean_lbl = " ".join(words_lbl) if len(words_lbl) >= 2 else \"\""""

new_tail = """    words_lbl = clean_lbl.split()
    if len(words_lbl) > 6:
        words_lbl = words_lbl[:6]
    INCOMPLETE_TAIL = {
        'thiết', 'ngân', 'của', 'và', 'với', 'trong', 'từ', 'là', 'để', 'cho',
        'nỗ', 'kẻ', 'các', 'những', 'một', 'đang', 'đã', 'sẽ', 'do', 'bởi',
        'vì', 'có', 'lại', 'cũng', 'rất', 'hơn', 'nhất', 'toàn', 'nghiêm',
        'đăng', 'điểm', 'lỗi'
    }
    COMPOUND_TAIL_VALID = {
        'thiết kế', 'thiết bị', 'ngân sách', 'ngân hàng', 'toàn cầu', 'nghiêm trọng',
        'đăng nhập', 'điểm yếu', 'khóa cửa', 'khai thác', 'tấn công', 'đột nhập',
        'xác thực', 'bảo mật', 'an ninh', 'rủi ro', 'phòng thủ', 'doanh nghiệp'
    }
    while len(words_lbl) >= 2:
        last = words_lbl[-1].lower()
        pair = f"{words_lbl[-2].lower()} {last}"
        if pair in COMPOUND_TAIL_VALID:
            break
        if last in INCOMPLETE_TAIL:
            words_lbl.pop()
        else:
            break
    # If the remaining words don't form a meaningful concept (>=2 words), drop the label completely
    clean_lbl = " ".join(words_lbl) if len(words_lbl) >= 2 else \"\""""

assert old_tail in code, "old_tail not found in scheduler.py"
code = code.replace(old_tail, new_tail)

old_recipes_data = """    elif recipe == "lock_unlock":
        if len(clauses) >= 2:
            data["status"] = " ".join(clauses[1].split()[:3]).upper()

    return data"""

new_recipes_data = """    elif recipe == "lock_unlock":
        if len(clauses) >= 2:
            data["status"] = " ".join(clauses[1].split()[:3]).upper()

    elif recipe == "orbit_system":
        data["center_node"] = " ".join(clauses[0].split()[:3]) if clauses else brief_info["label"]
        if len(clauses) >= 2:
            data["satellites"] = [" ".join(c.split()[:3]) for c in clauses[1:4]]
        else:
            data["satellites"] = [" ".join(w.split()[:2]) for w in clauses[:2]]
        data["label"] = brief_info["label"]

    elif recipe == "layered_onion":
        data["core_text"] = " ".join(clauses[0].split()[:3]) if clauses else brief_info["label"]
        if len(clauses) >= 2:
            data["layers"] = [" ".join(c.split()[:3]) for c in clauses[1:4]]
        else:
            data["layers"] = [" ".join(w.split()[:2]) for w in clauses[:2]]
        data["label"] = brief_info["label"]

    elif recipe == "stack_pile":
        data["layers"] = [" ".join(c.split()[:3]) for c in clauses[:4]]
        data["label"] = brief_info["label"]

    elif recipe == "puzzle_snap":
        data["solution_text"] = " ".join(clauses[0].split()[:3]) if clauses else brief_info["label"]
        data["label"] = brief_info["label"]

    elif recipe == "steps_ladder":
        data["steps"] = [" ".join(c.split()[:3]) for c in clauses[:4]]
        data["label"] = brief_info["label"]

    elif recipe == "stack_cards":
        data["items"] = [" ".join(c.split()[:4]) for c in clauses[:3]]
        data["label"] = brief_info["label"]

    elif recipe == "hub_spoke":
        data["center_node"] = " ".join(clauses[0].split()[:3]) if clauses else brief_info["label"]
        if len(clauses) >= 2:
            data["spokes"] = [" ".join(c.split()[:3]) for c in clauses[1:5]]
        data["label"] = brief_info["label"]

    return data"""

assert old_recipes_data in code, "old_recipes_data not found in scheduler.py"
code = code.replace(old_recipes_data, new_recipes_data)

target_file.write_text(code, encoding="utf-8")
print("scheduler.py updated successfully!")
