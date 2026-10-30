import pathlib
t = pathlib.Path("editor/motion/engine/particles.js").read_text(encoding="utf-8")
lines = t.splitlines()
for i, l in enumerate(lines):
    if "calculateOdometer" in l:
        for j in range(i, min(len(lines), i+30)):
            print(f"{j+1:3d}: {lines[j].encode('ascii', 'replace').decode()}")
        break
