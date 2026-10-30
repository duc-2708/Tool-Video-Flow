with open('docs/PROCESS.md', 'r', encoding='utf-8') as f:
    text = f.read()

entry = '''| 2026-10-29 | Giai đoạn 8 - Bước (b): Duyệt prompt trong Streamlit + Kết nối hạ tầng cổng AI/Nhập tay + Cache: (1) Xây dựng pipeline/ai_clip_manager.py quản trị vòng đời clip AI: hỗ trợ 3 chế độ AI_CLIP_MODE (off|auto|manual), kiểm tra thư mục ai_clips_manual/ copy vào clips/ kèm metadata nhãn AI, cache hit dựa trên sha256(prompt+model+seconds), tính toán chi phí và thời gian dự kiến (estimate_ai_clips_cost); (2) Tích hợp giao diện duyệt prompt trong Streamlit (app/views/ai_video.py): hiển thị bảng Scene Director, cho phép xem và sửa prompt_en/negative_en, nút 'Đã duyệt', nút 'Bỏ qua clip, dùng motion' tự động chuyển sang fallback_recipe, khu vực tải trực tiếp video vào ai_clips_manual/scene_{id}.mp4; (3) Cấu hình AI_CLIP_STALL_SEC=120 (chống treo job gateway quá lâu); (4) Kiểm chứng thực tế trên dự án auto-cong-nghe-d56d3ebe: mode off tự động fallback về motion với recipe, mode manual copy thành công clip mẫu sang clips/scene_1_ai_manual.mp4 với nhãn AI; (5) Bộ test unit tests/test_ai_clip_manager.py đạt 6/6 passed, toàn bộ suite 52/52 passed 100%. | APP/pipeline/ai_clip_manager.py, app/views/ai_video.py, config/settings.py, .env.example, tests/test_ai_clip_manager.py, output/auto-cong-nghe-d56d3ebe/; ROOT/docs/PROCESS.md | Hoàn thành Bước (b) Giai đoạn 8: Duyệt prompt trong Streamlit, nhập tay clip AI và quản lý hạ tầng cổng |'''

# Marker mục 2
marker2 = '| 2026-10-29 | Giai đoạn 8 - Bước (a): Scene Director + Validator + Hợp nhất Visual Planner:'
assert marker2 in text, 'marker2 not found'
text = text.replace(marker2, f'{entry}\n{marker2}', 1)

# Marker mục 15
marker15 = '| 2026-10-29 | Giai đoạn 8 - Bước (a): Scene Director + Validator + Hợp nhất Visual Planner:'
assert marker15 in text, 'marker15 not found'
text = text.replace(marker15, f'{entry}\n{marker15}', 1)

with open('docs/PROCESS.md', 'w', encoding='utf-8') as f:
    f.write(text)
print('Successfully updated PROCESS.md for Phase 8 step (b)')
