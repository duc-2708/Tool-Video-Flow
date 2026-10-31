from pathlib import Path

target_file = Path("app/views/render.py")
code = target_file.read_text(encoding="utf-8")

old_str = """    # Kiểm tra trạng thái LLM Planner v3
    status_file = project / "planner_status.json"
    if status_file.is_file():
        try:
            p_status = read_json(status_file)
            if not p_status.get("llm_ok", True):
                st.warning("⚠️ Planner AI lỗi: đang dùng recipe suy luận theo từ khóa")
        except Exception:
            pass"""

new_str = """    # Kiểm tra trạng thái LLM Planner v3
    status_file = project / "planner_status.json"
    if status_file.is_file():
        try:
            p_status = read_json(status_file)
            if not p_status.get("llm_ok", True):
                st.warning("⚠️ Planner AI lỗi: đang dùng recipe suy luận theo từ khóa")
        except Exception:
            pass

    # Hiển thị tóm tắt Visual Bible (Kế hoạch hình ảnh tổng thể)
    bible_file = project / "visual_bible.json"
    bible_status_file = project / "visual_bible_status.json"
    if bible_file.is_file():
        try:
            b_data = read_json(bible_file)
            b_status = read_json(bible_status_file) if bible_status_file.is_file() else {}
            if b_status.get("fallback_used"):
                st.warning(f"⚠️ Visual Bible: Đang dùng quy tắc dự phòng ({b_status.get('reason', '')})")
            with st.expander("🌐 Kế hoạch hình ảnh tổng thể (Visual Bible)"):
                worlds_txt = "; ".join(f"{w.get('kind')} ({w.get('reason')})" for w in b_data.get("worlds", []))
                actors_txt = "; ".join(f"{a.get('type')} ({a.get('role')})" for a in b_data.get("persistent_actors", []))
                chaps_txt = " · ".join(f"{ch.get('kicker')}: {ch.get('title')}" for ch in b_data.get("structure", {}).get("chapters", []))
                st.markdown(f"- **Thế giới:** {worlds_txt}")
                st.markdown(f"- **Vật thể xuyên suốt:** {actors_txt}")
                st.markdown(f"- **Cấu trúc:** {chaps_txt}")
                pm = b_data.get("progress_metaphor", {})
                if pm.get("type") != "none":
                    st.markdown(f"- **Tiến độ ẩn dụ:** `{pm.get('type')}` ({', '.join(pm.get('items', []))})")
        except Exception:
            pass"""

assert old_str in code, "old_str not found in render.py"
code = code.replace(old_str, new_str)
target_file.write_text(code, encoding="utf-8")
print("app/views/render.py updated with Visual Bible UI!")
