import pathlib
t = pathlib.Path("editor/motion/runtime.js").read_text(encoding="utf-8")
lines = t.splitlines()
for i, l in enumerate(lines):
    if "countUp" in l:
        print(f"Line {i+1}: {l.encode('ascii', 'replace').decode()[:120]}")
