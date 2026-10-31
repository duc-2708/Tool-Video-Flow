import re
import sys
sys.stdout.reconfigure(encoding="utf-8")
from agents.visual_diversity import CONCEPTS, GENERIC
from agents.presentation import clean_semantic_label, valid_card, labels_are_duplicate, card_phrase

context = 'Điều này giống như việc gắn cửa cuốn tự động thông minh vào một ngôi nhà cổ kỹ thuật cũ kỹ.'
used = ['Phòng máy chủ', 'Cửa cuốn tự động']
used_set = {s.casefold() for s in used}

print("1. Checking CONCEPTS...")
candidates = []
for phrase in CONCEPTS:
    m = re.search(r'(?<!\w)' + re.escape(phrase) + r'(?!\w)', context, re.I)
    if m:
        label = m[0] if len(m[0].split()) >= 3 else ' '.join(('Bảo vệ' if phrase in {'danh tính', 'phòng thủ'} else ('Phân tích' if phrase in {'điểm yếu', 'lỗ hổng phần mềm'} else 'Vấn đề'), m[0]))
        candidates.append(label)
print("  candidates from CONCEPTS:", candidates)

print("2. Checking clauses in context...")
for c in re.split(r'(?<!\d)\.|\.(?!\d)|[!?;:—]', context):
    print("  split part:", repr(c), "valid_card:", valid_card(c))
    if valid_card(c):
        candidates.append(c.strip(' ,:'))

phrase = card_phrase('', context, used=used_set)
print("  card_phrase:", repr(phrase))
if not GENERIC.fullmatch(phrase):
    candidates.append(phrase)

print("  all candidates:", candidates)

for c in candidates:
    cleaned = clean_semantic_label(c)
    v = valid_card(cleaned)
    dup = cleaned.casefold() in used_set or any(labels_are_duplicate(cleaned, u) for u in used_set)
    print(f"  candidate '{c}' -> cleaned '{cleaned}', valid={v}, dup={dup}")

print("3. Checking clauses splitting...")
clauses = re.split(r'(?<!\d)\.|\.(?!\d)|[!?;:—–,\(\)“”\"\[\]]|\b(?:và|hoặc|nhưng|mà|để|như|khi|sau khi|trong khi|thay vì|bởi vì)\b', context, flags=re.I)
for cl in clauses:
    cl_clean = clean_semantic_label(cl)
    v = valid_card(cl_clean)
    dup = cl_clean.casefold() in used_set or any(labels_are_duplicate(cl_clean, u) for u in used_set)
    print(f"  clause '{cl}' -> clean '{cl_clean}', valid={v}, dup={dup}")
    words = cl.strip().split()
    if len(words) >= 3:
        for n_words in (4, 3):
            for idx in range(min(len(words) - n_words + 1, 3)):
                sub = clean_semantic_label(' '.join(words[idx:idx+n_words]))
                sv = valid_card(sub)
                sdup = sub.casefold() in used_set or any(labels_are_duplicate(sub, u) for u in used_set)
                print(f"    sub '{sub}', valid={sv}, dup={sdup}")
