import pathlib
lines = pathlib.Path("editor/motion/recipes/vocabulary.js").read_text(encoding="utf-8").splitlines()
in_func = False
func_lines = []
for l in lines:
    if "function renderSlotCounter" in l:
        in_func = True
    if in_func:
        func_lines.append(l)
        if len(func_lines) > 90:
            break
for i, l in enumerate(func_lines):
    print(f"{i+1:2d}: {l.encode('ascii', 'replace').decode()}")
