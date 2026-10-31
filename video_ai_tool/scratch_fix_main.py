from pathlib import Path
p = Path('tools/audit_video.py')
text = p.read_text(encoding='utf-8')
old_line = "res = audit_project(target_dir)"
new_line = "force_flag = ('--force' in sys.argv)\n    res = audit_project(target_dir, force=force_flag)"
assert old_line in text, "old_line not found"
text = text.replace(old_line, new_line, 1)
p.write_text(text, encoding='utf-8')
print("Updated main() in audit_video.py with force flag support!")
