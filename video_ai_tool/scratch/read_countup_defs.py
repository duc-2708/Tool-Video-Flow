import pathlib
t = pathlib.Path("editor/motion/runtime.js").read_text(encoding="utf-8")
lines = t.splitlines()
print("runtime.js lines 5-15:")
for l in lines[4:15]:
    print(l.encode("ascii", "replace").decode())

t2 = pathlib.Path("editor/motion/engine/recipes.js").read_text(encoding="utf-8")
lines2 = t2.splitlines()
print("\nrecipes.js renderStatNumber:")
for i, l in enumerate(lines2):
    if "function renderStatNumber" in l:
        for j in range(i, min(len(lines2), i+45)):
            print(f"{j+1:3d}: {lines2[j].encode('ascii', 'replace').decode()}")
        break
