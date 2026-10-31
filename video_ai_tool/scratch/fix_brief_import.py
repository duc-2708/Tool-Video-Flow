from pathlib import Path

target = Path("pipeline/assets.py")
code = target.read_text(encoding="utf-8")
code = code.replace("from schemas.research import ResearchBrief", "from schemas.research_brief import ResearchBrief")
target.write_text(code, encoding="utf-8")
print("pipeline/assets.py import fixed!")
