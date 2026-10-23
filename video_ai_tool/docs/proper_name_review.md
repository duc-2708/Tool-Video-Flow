# Tên riêng trong Explainer v2

`agents/proper_names.py` cung cấp cùng bộ dò cho lời đọc sự kiện, câu nền và
đồ họa. Từ đầu câu/mệnh đề/dòng/bullet không tự trở thành tên riêng. Whitelist
từ Việt thông dụng ưu tiên hơn viết hoa. Cụm viết hoa và token nước ngoài như
Cambridge, Meta, OpenAI, GPT-5 vẫn được đối chiếu, kể cả ở đầu câu. Đây là bộ
lọc ứng viên bằng quy tắc, không phải NER đầy đủ.

- `sentence_grounding` nhóm 1: câu event vẫn phải có fact_id, số liệu và tên
  có căn cứ. Tên sai được thử sửa riêng câu một lần bằng fact_vi đã tham chiếu;
  không có fact hợp lệ thì giữ lỗi cứng. Không gọi Gemini cho phép sửa cục bộ này.
- `sentence_background_names` nhóm 3: tên riêng ngoài brief trong
  explain/opinion/cta → “ví dụ nền, nên kiểm tra lại”, lưu review_notes của cảnh.
- Các số liệu sự kiện hoặc khẳng định sự kiện giả nhãn nền vẫn được kiểm tra.

Revalidate bản nháp dùng giá trị EditPlan mà validate_plan trả về. Các lỗi
sentence_grounding cũ đã hết được bỏ khỏi danh sách lỗi đang hoạt động; bản
nháp gốc vẫn giữ thông báo cũ để truy vết, bản phục hồi lưu riêng trước khi dùng.
