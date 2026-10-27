from pathlib import Path
import re

app_render_path = Path("app/views/render.py")
code = app_render_path.read_text(encoding="utf-8")

needle = "    if result.get('quality_summary'):"
replacement = """    if result.get('audit_failed') or (project / 'layout_report.json').is_file():
        try:
            lr_path = project / 'layout_report.json'
            if lr_path.is_file():
                lr_data = read_json(lr_path)
                if not lr_data.get('overall_all_passed', True):
                    st.error('🚨 CẢNH BÁO ĐỎ: Phát hiện lỗi kiểm định bố cục hoạt họa (layout_report.json) sau 2 lượt tự sửa! Hãy kiểm tra tràn lề hoặc đè phụ đề.')
        except Exception:
            pass
    if result.get('quality_summary'):"""

if needle in code and "CẢNH BÁO ĐỎ" not in code:
    code = code.replace(needle, replacement, 1)
    app_render_path.write_text(code, encoding="utf-8")
    print("Updated app/views/render.py")
