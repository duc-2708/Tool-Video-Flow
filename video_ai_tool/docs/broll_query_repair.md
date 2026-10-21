> Cập nhật: chính sách mới trong [director_validation_policy.md](director_validation_policy.md) thay thế phần retry chất lượng/query trong tài liệu này. Sửa cấu trúc và query trong validation chỉ dùng code, không gọi Gemini.

# B-roll query: giới hạn, sửa cục bộ và chống trùng

## Nguyên nhân

Trước sửa, `create_story_plan()` gán `word.broll_query` cho mọi shot của cảnh; `apply_words()` cũng gán cùng scalar nếu Gemini không trả mảng `shot_queries`. Không có bước làm sạch trước Shot/Pydantic, nên một chuỗi dài được nhân thành nhiều lỗi. Không có lệnh gán trực tiếp từ `topic_discovery.search_queries` hoặc style preset vào Shot.query.

Hiện tại scalar chỉ là gợi ý đầu vào. `normalize_plan_structure()` mở rộng thành query độc lập cho từng shot, làm sạch và biến thể hóa trước schema. Lượt viết 2 dùng `word.shot_queries[i]`, không broadcast scalar. Người hóa và retry vẫn gọi chung normalizer trước schema/apply_words. Kiểm tra cuối `validate_plan` chuẩn hóa toàn video, giữ query của các cảnh không được yêu cầu viết lại trong reference.

## Sanitizer

`agents/broll_queries.py::sanitize_broll_query(query, scene_context, provider=None, diagnostics=None)`:

- Bỏ dấu/ký tự lạ, dịch một số cụm Việt phổ biến trong b-roll, chọn tối đa bốn từ stock tiếng Anh cụ thể; loại tên hãng/sản phẩm/người nổi tiếng. Vốn từ stock được giới hạn để không coi mọi chuỗi Latin là tiếng Anh.
- Nếu không còn hai từ có nghĩa, chỉ gọi Gemini sửa query này một lần. Query API hỏng/timeout/không đạt dùng query dự phòng theo cảnh; không làm sinh lại kịch bản.
- Dùng tập query đã xuất hiện trong video để chọn bối cảnh/hành động khác, sau đó góc quay/ánh sáng nếu cần; không thêm số thứ tự hoặc lặp tên chủ đề.
- Query sửa được ghi old → new vào UTF-8 log và review_notes, không chèn vào lời đọc/facts. Không đổi narration, timing, loại cảnh hay fact_ids.
- Shot validator cũng có sanitizer trước kiểm tra chuỗi. Schema Scene không tự khử trùng lặp khi đọc Assets cũ để tránh thay đổi query/fingerprint chỉ vì đọc lại artifact; Director khử trùng lặp ở cấp toàn plan.

## Hồi quy project auto-cong-nghe-ace8ccb3

File gốc `output/auto-cong-nghe-ace8ccb3/edit_plan.draft.json` có **plan=null**, không có nguyên JSON Gemini/narration/shot đầy đủ. Nó giữ 19 đường dẫn lỗi query và biểu diễn input bị Pydantic rút gọn. Không thể nói rằng đã lấy lại nguyên plan bị mất từ file này.

Test đọc đúng file thật và bản snapshot trong `tests/fixtures/auto-cong-nghe-ace8ccb3/`. Từ brief/config hiện có, tái dựng blueprint với đúng 19 vị trí shot, đưa biểu diễn query lỗi đã lưu vào các vị trí đó, rồi normalize → Pydantic → validate căn cứ/timing. Kết quả có 19 query khác nhau, mỗi query 2–4 từ Latin. Nội dung dựng cho hồi quy lấy từ fact đã có; check_style=False vì narration lượt 2 thật không được lưu, không giả định khôi phục được văn phong gốc.

Test mock ba lượt chạy validation đầy đủ, giữ nguyên narration/facts, và không cần retry toàn kịch bản khi query dài. Test khác bao gồm tiếng Việt/có dấu, brand, Gemini sửa thành công, Gemini lỗi rồi fallback, chống trùng và sửa riêng cảnh có reference. Các snapshot không chứa `.env`.

Các lượt mới giữ `candidate` trước Pydantic để bản nháp không mất toàn bộ plan nếu validation khác thất bại.
