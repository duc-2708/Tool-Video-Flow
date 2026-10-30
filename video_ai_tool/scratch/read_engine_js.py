import pathlib
lines = pathlib.Path("editor/motion/scenes/engine.js").read_text(encoding="utf-8").splitlines()
for i, l in enumerate(lines):
    if "MotionVocabulary" in l:
        print("\n".join(lines[max(0, i-5):min(len(lines), i+15)]))
        break
