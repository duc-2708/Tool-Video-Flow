# Hồ sơ phong cách và kế hoạch theo nội dung

- Style Learner trả `entities_in_video`: cụm tên riêng đầy đủ, không tách âm tiết. Hồ sơ lưu `reference_entities` chỉ để lọc tại máy; danh sách này và corpus đối chiếu không được đưa vào prompt Director. Không suy đoán thực thể từ chữ viết hoa đầu câu. Các bản thô cũ thiếu danh sách vẫn parse offline, không gọi lại Gemini để bổ sung.
- Chỉ thay đúng nguyên cụm, theo ranh giới từ. Các từ/cụm thông dụng như giải thích, sử dụng, phân tích, đánh giá, cao trào, chia nhỏ, ví dụ được giữ nguyên. Nếu kết quả tạo placeholder dính âm tiết hoặc hơn hai placeholder/câu, dùng bản gốc đã bỏ tên riêng và số liệu, kèm cảnh báo.
- `content_timed=true` đánh dấu kế hoạch mới đã căn theo lời đọc: `max(words / 2.6 + 0.8, 2.5)` giây/cảnh. Số shot là `min(4, max(1, round(duration / shot_seconds.mean)))`. `requested_duration_sec` giữ yêu cầu ban đầu, `target_duration_sec`/tổng shot phản ánh kế hoạch thực tế. Không kéo cảnh ít chữ dài ra để đủ yêu cầu.
- `planning_duration=true` đánh dấu timing ước tính của shot trong Director. Shot ước tính có thể nằm ngoài 1.5–4s để giữ đúng số slot. Assets bỏ cờ này và căn lại theo audio thật, vẫn đảm bảo shot resolved 1.5–4s. Lời đọc/fact không thay đổi trong bước căn timing.
- Query lỗi/trùng ưu tiên từ khóa nội dung cảnh và fact, với ánh xạ từ khóa tiếng Việt sang stock tiếng Anh; thay đổi góc máy trên cùng chủ thể để tránh trùng. Không xoay vòng sang chủ thể không liên quan. Kho query theo chủ đề chỉ là fallback cuối khi không trích được từ khóa. Không gọi thêm Gemini cho bước sửa này.
- Tiêu đề dùng tiếng Việt. Clip AI tắt thì shot `ai_video` trở về `stock_video`; query được giữ/sửa theo cùng nội dung.
- Khi ít hơn 6 fact hoặc chỉ 1 nhà xuất bản độc lập, Research thử mở rộng đúng một lần: tối đa 4 truy vấn đồng nghĩa, lấy thêm tối đa 4 nguồn mới. Nếu có nguồn mới, rút và đối chiếu lại fact; giữ fact đã qua đối chiếu nếu mở rộng thất bại. Lưu thông tin mở rộng trong `sources.json`, truy vấn vào brief. Dữ liệu vẫn mỏng thì tiếp tục với cảnh báo, không bịa cho đủ số lượng.

UI Research hiển thị lượt mở rộng và cảnh báo dữ liệu mỏng. UI Edit Plan/report hiển thị thời lượng yêu cầu so với thực tế; khi quá ngắn, gợi ý tăng số nguồn hoặc chọn chủ đề khác.

Đã dựng lại hồ sơ công nghệ tại máy:

```powershell
.\.venv\Scripts\python.exe -m pipeline.style_learner --category "công nghệ" --analyze --from-raw --max-sec 180
```

Fixture hồi quy gồm profile hỏng trước sửa, ba raw phân tích công nghệ, bản kế hoạch 3 cảnh Guardian tại `output/auto-cong-nghe-c8813fcb/edit_plan.json` (project này không có draft tương ứng khi kiểm tra), và draft Guardian có thật ở `output/auto-cong-nghe-8a211210/edit_plan.draft.json`. Các file project gốc không bị ghi lại khi chạy test.
