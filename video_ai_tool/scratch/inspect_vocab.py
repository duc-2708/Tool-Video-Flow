import pathlib
import re

t = pathlib.Path("editor/motion/recipes/vocabulary.js").read_text(encoding="utf-8")
matches = re.findall(r"window\.MotionVocabulary\[['\"](\w+)['\"]\]\s*=", t)
print(f"Total keys assigned to window.MotionVocabulary: {len(matches)}")
print("Keys:", matches)
