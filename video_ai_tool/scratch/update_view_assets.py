from pathlib import Path

target_file = Path("app/views/assets.py")
code = target_file.read_text(encoding="utf-8")

old_str = """    st.dataframe([{"Cảnh": scene.scene_id, "Audio (giây)": scene.audio_duration_sec,
                   "Trạng thái giọng": "IM LẶNG — cần thử lại" if scene.audio_silent else "Đã có" if scene.audio_path else "TTS lỗi — cần thử lại",
                   "Số shot": len(scene.shots), "Fallback": sum(shot.fallback for shot in scene.shots)}
                  for scene in manifest.scenes], hide_index=True)"""

new_str = """    st.dataframe([{"Cảnh": scene.scene_id, "Audio (giây)": scene.audio_duration_sec,
                   "Trạng thái giọng": "IM LẶNG — cần thử lại" if scene.audio_silent else "Đã có" if scene.audio_path else "TTS lỗi — cần thử lại",
                   "Số shot": len(scene.shots), "Fallback": sum(shot.fallback for shot in scene.shots)}
                  for scene in manifest.scenes], hide_index=True)

    # Hiển thị tóm tắt Visual Bible (Kế hoạch hình ảnh tổng thể)
    bible_file = project / "visual_bible.json"
    bible_status_file = project / "visual_bible_status.json"
    if bible_file.is_file():
        try:
            b_data = read_json(bible_file)
            b_status = read_json(bible_status_file) if bible_status_file.is_file() else {}
            with st.expander("🌐 Visual Bible (Thế giới, Vật thể & Cấu trúc)", expanded=False):
                if b_status.get("fallback_used"):
                    st.warning(f"⚠️ **Visual Bible:** Đang dùng quy tắc dự phòng (fallback) — {b_status.get('reason', '')}")
                else:
                    st.success("✅ **Visual Bible:** Khởi tạo thành công bởi AI Router")
                
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    st.markdown("**Thế giới không gian (Worlds):**")
                    for w in b_data.get("worlds", []):
                        st.markdown(f"- `{w.get('kind')}`: {w.get('reason')} *(Khu vực: {', '.join(w.get('zones', []))})*")
                    pm = b_data.get("progress_metaphor", {})
                    if pm.get("type") != "none":
                        st.markdown(f"**Ẩn dụ tiến độ ({pm.get('type')}):** {', '.join(pm.get('items', []))}")
                with col_b2:
                    st.markdown("**Vật thể xuyên suốt (Persistent Actors):**")
                    for a in b_data.get("persistent_actors", []):
                        st.markdown(f"- `{a.get('type')}` ({a.get('id')}): {a.get('role')} *[Trạng thái: {', '.join(a.get('states', []))}]*")
                    chaps = b_data.get("structure", {}).get("chapters", [])
                    if chaps:
                        st.markdown("**Cấu trúc phân đoạn (Chapters):**")
                        for ch in chaps:
                            st.markdown(f"- **{ch.get('kicker')}**: {ch.get('title')} *(Cảnh: {', '.join(map(str, ch.get('scene_ids', [])))})*")
        except Exception as exc:
            diagnostics.record_exception(exc, "Lỗi đọc visual_bible.json trong UI Assets")"""

assert old_str in code, "old_str not found in assets.py view"
code = code.replace(old_str, new_str)
target_file.write_text(code, encoding="utf-8")
print("app/views/assets.py updated with Visual Bible UI!")
