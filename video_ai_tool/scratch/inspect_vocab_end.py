import pathlib
t = pathlib.Path("editor/motion/recipes/vocabulary.js").read_text(encoding="utf-8")
lines = t.splitlines()
print("\n".join(lines[-40:]))
