import re
from pathlib import Path

scenes_dir = Path("editor/motion/scenes")
for p in scenes_dir.glob("*/scene.html"):
    content = p.read_text(encoding="utf-8")
    new_content = re.sub(r'viewBox=["\']0 0 900 1100["\']', 'viewBox="0 0 1080 1920" width="1080" height="1920"', content)
    if new_content != content:
        p.write_text(new_content, encoding="utf-8")
        print(f"Updated {p.parent.name}")
