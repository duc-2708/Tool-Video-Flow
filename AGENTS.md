# Quy tắc bắt buộc cho AI và người làm dự án

- BẮT BUỘC đọc `docs/PROCESS.md` từ đầu đến cuối trước khi sửa bất kỳ thứ gì.
- Gốc repo là thư mục chứa file này; mã ứng dụng và nơi chạy Python nằm trong `video_ai_tool/`.
- Sau MỖI thay đổi (thêm/sửa/xóa tính năng, đổi luật/config, sửa lỗi), cập nhật đúng mục liên quan trong `docs/PROCESS.md`.
- Thêm một dòng changelog mới nhất ở trên và cập nhật checklist trong cùng tài liệu, rồi mới báo hoàn thành.
- Chưa cập nhật tài liệu = chưa xong; không chỉ thêm changelog mà để nội dung cũ mâu thuẫn.
- Không in, log, commit khóa API/token hoặc nội dung `.env`; dùng redaction và dữ liệu giả trong test.
- Không thêm/đổi luật chặn nếu chưa có rule_id và nhóm rõ ràng: 1 chặn, 2 tự sửa, 3 cảnh báo.
- Tách event có căn cứ khỏi explain/opinion/cta; không dùng luật chất lượng để chặn ngoài nhóm đã công bố.
- Mọi sửa lỗi phải có test hồi quy; dùng mock API, giữ fixture thật khi có, không bịa dữ liệu đã mất.
- Chạy pytest trước khi báo xong: từ `video_ai_tool/`, dùng `.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp -p no:cacheprovider`.
- Báo đúng kết quả, giới hạn kiểm chứng và các mục CHƯA XÁC NHẬN; không nhận test mock là API thật thành công.
- Không thay đổi hành vi ngoài phạm vi yêu cầu; tái sử dụng module/hàm có sẵn.
- Không tự tạo request trả phí; không gửi lại POST/job chưa rõ remote ID để thử lỗi.
- Giữ nguyên input Render, tôn trọng hash/checkpoint/atomic I/O/locks; không sửa status/hash để ép pipeline chạy.
- Không tải/dùng lại video mạng xã hội của người khác; mẫu chỉ học phong cách, không sao chép nội dung.
- Khi doc và code mâu thuẫn: báo người dùng, không tự đoán hoặc âm thầm đổi hành vi.
