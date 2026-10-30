with open('tools/audit_video.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '    scenes = plan.get("scenes", [])'
replacement = '''    scenes = plan.get("scenes", [])
    brief = None
    brief_path = project_dir / "brief.json"
    if brief_path.is_file():
        try:
            from schemas.research_brief import ResearchBrief
            brief = ResearchBrief.model_validate_json(brief_path.read_text(encoding="utf-8"))
        except Exception:
            brief = None'''

assert target in text, 'Target not found'
text = text.replace(target, replacement, 1)

with open('tools/audit_video.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Successfully fixed brief loading in audit_video.py')
