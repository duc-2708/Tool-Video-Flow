# Gemini: lỗi tạm thời và tiếp tục Director

Lớp dùng chung thử lại 429/500/502/503/504, `DEADLINE_EXCEEDED`, `UNAVAILABLE`, timeout và lỗi mạng tạm thời. Mỗi yêu cầu tối đa 6 lần gọi: lần đầu + 5 lần thử lại, chờ 3/6/12/24/48 giây cộng jitter 0–1 giây. SDK không tự tạo vòng retry thứ hai. 400/401/403/404 dừng ngay; cơ chế thử lại schema sau HTTP 400 trước đây đã bỏ theo chính sách mới. Lỗi JSON/nội dung là kiểm tra riêng của từng agent.

Sau 2 lần deadline/timeout, lượt tiếp theo dùng prompt gọn: giữ chỉ dẫn gốc, các quy tắc phong cách chính, giảm nguồn còn tổng 12000 ký tự và ưu tiên tối đa 12 fact. Tất cả fact đang tham chiếu được giữ kể cả vượt mức mềm 12; ID không đổi, không cắt lời đọc/cảnh đã kiểm tra. Sau khi prompt gọn vẫn timeout, chuyển `GEMINI_FALLBACK_MODEL` nếu đã cấu hình. Model dự phòng chia sẻ cùng ngân sách 5 retry, không mở thêm vòng. Nếu vẫn lỗi thì báo rõ và giữ checkpoint.

Các mặc định nằm trong `.env.example`; `.env` thật không được sửa tự động:

```dotenv
GEMINI_TIMEOUT_SEC=120
GEMINI_FALLBACK_MODEL=
```

Điền tên model dự phòng có quyền sử dụng nếu cần. Timeout này độc lập `REQUEST_TIMEOUT_SEC` của nguồn HTTP. Style Learner vẫn dùng timeout video riêng `STYLE_TIMEOUT_SEC`.

Director ba lượt ghi `output/<project>/director_state.json` bằng atomic I/O sau dàn ý, bản viết và bản người hóa cuối đã kiểm tra. File gồm dữ liệu, hash, thời điểm hoàn tất và lỗi lượt đang dở. Chạy lại cùng project/brief/cấu hình/prompt sẽ dùng lại các lượt đã xong, không gọi lại chúng. Nếu brief/model/phong cách/giọng/thời lượng/prompt/chính sách kiểm tra đổi, checkpoint cũ bị vô hiệu hóa. Mỗi lượt đọc lại vẫn được kiểm tra schema/hash; nội dung cuối vẫn phải qua luật chống bịa.

CLI chạy lại Director trên cùng brief hoặc dùng `pipeline.run_all --resume <project>`. UI chọn project và Tiếp tục (pipeline), hoặc Tạo Edit Plan lại với cùng cấu hình. Chưa có checkpoint từ phiên bản trước thì lượt đầu chạy mới vẫn phải tạo nó. Hết retry ở Người hóa giữ bản viết để lần sau tiếp tục, không tự coi là đã hoàn tất lượt Người hóa.

Thông báo `Gemini quá tải (504), thử lại lần N/5 sau X giây` đi qua callback tiến trình CLI/UI. Log UTF-8 ghi từng lần: code, model, số ký tự prompt, token ước lượng, thời gian phản hồi, rút gọn/chuyển model và traceback đã che key. Director dùng `logs/director_errors.log`; các caller khác dùng Diagnostics của chúng. Không ghi toàn bộ prompt hoặc nội dung `.env`.
