import re
import sys
sys.stdout.reconfigure(encoding="utf-8")
from agents.presentation import clean_semantic_label, valid_card, labels_are_duplicate

context = 'Điều này giống như việc gắn cửa cuốn tự động thông minh vào một ngôi nhà cổ kỹ thuật cũ kỹ.'
used = ['Phòng máy chủ', 'Cửa cuốn tự động']
used_set = {s.casefold() for s in used}

clauses = re.split(r'(?<!\d)\.|\.(?!\d)|[!?;:—–,\(\)“”\"\[\]]|\b(?:và|hoặc|nhưng|mà|để|như|khi|sau khi|trong khi|thay vì|bởi vì)\b', context, flags=re.I)
found = None
for cl in clauses:
    words = cl.strip().split()
    if len(words) >= 3:
        for n_words in (4, 3):
            for idx in range(len(words) - n_words + 1):
                sub = clean_semantic_label(' '.join(words[idx:idx+n_words]))
                if sub and valid_card(sub) and sub.casefold() not in used_set and not any(labels_are_duplicate(sub, u) for u in used_set):
                    found = sub[:1].upper() + sub[1:]
                    break
            if found: break
    if found: break

print("Found without min(..., 3) restriction:", repr(found))
