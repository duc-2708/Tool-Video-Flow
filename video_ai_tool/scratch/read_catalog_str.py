import pathlib
lines = pathlib.Path("editor/motion/registry.py").read_text(encoding="utf-8").splitlines()
for i, l in enumerate(lines):
    if "def catalog_prompt_string" in l:
        for j, line in enumerate(lines[i:i+40]):
            print(f"{i+j+1:3d}: {line.encode('ascii', 'replace').decode()}")
        break
