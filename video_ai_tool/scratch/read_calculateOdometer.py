import pathlib
t = pathlib.Path("editor/motion/engine/recipes.js").read_text(encoding="utf-8")
lines = t.splitlines()
print("recipes.js lines 1-55:")
for l in lines[:55]:
    print(l.encode("ascii", "replace").decode())
