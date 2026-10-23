# Đồ họa và Explainer v2

`visual.sentence_index` liên kết shot với câu (đếm từ 1). Nếu không có, dùng
nhãn `visual.content_type`; kế hoạch cũ mặc định là event. Thẻ nguồn luôn
được kiểm tra như dữ liệu sự kiện. Kiểm tra tên riêng trên từng trường riêng,
không nối cuối nhãn này với đầu nhãn khác.

Director: `visual_grounding` nhóm 1 áp dụng cho event; `visual_background`
nhóm 3 cảnh báo ví dụ nền, tên riêng và số chưa làm tròn/thiếu từ ước lượng.
`visual_structure` nhóm 2 khôi phục nhãn đảo thứ tự từ cụm có trong lời đọc.
Không thay đổi luật căn cứ của lời đọc sự kiện.

Render: kiểm tra trên bản sao trong bộ nhớ. Thẻ event sai căn cứ chuyển sang
text_focus trung tính; ví dụ nền giữ nguyên kèm cảnh báo. Mẫu không dựng được
dùng nền màu; lỗi mẫu không làm mất cả video. Lỗi audio/Assets hỏng vẫn cần sửa.

Edit Plan → “Kiểm tra đồ họa theo từng shot” hiển thị cảnh/shot, dữ liệu và cảnh
báo. Hai nút “Dùng bản trung tính”, “Giữ nguyên (tôi chịu trách nhiệm)” không
gọi API. Quyết định lưu UTF-8 qua atomic_io trong `visual_decisions.json`, khóa
theo scene/shot và hash lời đọc; thay lời đọc làm lựa chọn cũ hết hiệu lực.
UI dùng danh sách shot resolved khi cùng lời đọc để hỗ trợ shot Assets thêm.

Đầu vào brief/edit_plan.resolved/audio/clips/credits không bị Render sửa.
Kết quả đối chiếu và lựa chọn đã áp dụng nằm trong `render/visual_review.json`,
`render/report.md` và cảnh báo của `render/preview.json` hoặc `final.json`.
Pipeline 1 nút đưa cảnh báo Render vào `report.md` cấp project như các bước khác.
