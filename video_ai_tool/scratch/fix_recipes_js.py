with open("editor/motion/engine/recipes.js", "r", encoding="utf-8") as f:
    c = f.read()

bad_str = "    d: M   L   L   V  C       C       Z,"
good_str = '    d: `M ${x + 35} ${y + 22} L ${x + 50} ${y + 14} L ${x + 65} ${y + 22} V ${y + 38} C ${x + 65} ${y + 54} ${x + 50} ${y + 64} ${x + 50} ${y + 64} C ${x + 50} ${y + 64} ${x + 35} ${y + 54} ${x + 35} ${y + 38} Z`,'

assert bad_str in c, "bad_str not found"
c = c.replace(bad_str, good_str)
with open("editor/motion/engine/recipes.js", "w", encoding="utf-8") as f:
    f.write(c)

import subprocess
res = subprocess.run(["node", "--check", "editor/motion/engine/recipes.js"], capture_output=True, text=True)
print("recipes.js syntax:", res.returncode, res.stderr)
