from pathlib import Path

p = Path("video_ai_tool/config/settings.py")
text = p.read_text(encoding="utf-8")

target = '    brand_logo_path: str = ""\n'
if target not in text:
    target = '    brand_logo_path: str = ""\r\n'

assert target in text, "target not found"

text = text.replace(target, target + '    slide_planner_model: str = ""\n', 1)
text = text.replace("'brand_logo_path',mode='before'", "'brand_logo_path','slide_planner_model',mode='before'")
text = text.replace("'brand_logo_path':''}", "'brand_logo_path':'','slide_planner_model':''}")

p.write_text(text, encoding="utf-8")
print("Updated settings.py successfully!")
