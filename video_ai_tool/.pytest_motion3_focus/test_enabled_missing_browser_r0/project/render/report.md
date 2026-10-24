# Kiểm tra đồ họa khi Render

- Cảnh 8, shot 1: dùng nền màu và chữ.
- Cảnh 1: Motion không sẵn sàng; dùng đồ họa Pillow hiện có. Kiểm tra Playwright/Chromium và logs/render_errors.log.
- Cảnh 1: motion_layout nhóm 3: dự phòng Pillow, chưa đo bố cục DOM.
- Cảnh 8: motion_layout nhóm 3: dự phòng Pillow, chưa đo bố cục DOM.

## Motion review_notes

- Cảnh 1, shot 1: motion_beats nhóm 2: không khớp từ khóa 'Mẫu kiểm thử'; chia nhịp theo shot.
- Cảnh 1: timing từ estimated_characters/estimated_characters; beats khớp sidecar, chưa chứng minh sai số audio ≤0,2s.
- Cảnh 8: timing từ estimated_characters/estimated_characters; beats khớp sidecar, chưa chứng minh sai số audio ≤0,2s.
- Cảnh 1: motion_layout nhóm 3: dự phòng Pillow, chưa đo bố cục DOM.
- Cảnh 8: motion_layout nhóm 3: dự phòng Pillow, chưa đo bố cục DOM.

Đầu vào Edit Plan, audio, clips và credits được giữ nguyên.
