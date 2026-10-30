import pathlib
lines = pathlib.Path("editor/motion/recipes/vocabulary.js").read_text(encoding="utf-8").splitlines()
for i, l in enumerate(lines[60:120], 61):
    print(f"{i+1:3d}: {l.encode('ascii', 'replace').decode()}")
