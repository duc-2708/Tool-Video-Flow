# Chính sách validation Director

Mặc định chỉ nhóm 1 được dừng hoặc gọi lại Gemini. Nhóm 2 sửa bằng code; nhóm 3 ghi cảnh báo. Quy tắc trong YAML có hiệu lực ở lượt dàn ý, viết, người hóa, retry và validate cuối. Không cần sửa prompt để đổi nhóm.

| ID | Nhóm | Luật | Kiểm tra | Tự sửa |
|---|---:|---|---|---|
| `fact_ids` | 1 | ID fact hợp lệ; cảnh nội dung có căn cứ | `fact_ids` | — |
| `forbidden_editorial` | 1 | Cụm kiểm chứng bị cấm còn sót sau xóa | `forbidden` | `clean_forbidden` |
| `grounding_claims` | 1 | Khẳng định/nhân quả được audit đối chiếu fact | `audit_claims` | — |
| `grounding_names_quotes` | 1 | Tên riêng/trích dẫn có căn cứ | `names_quotes` | — |
| `grounding_numbers` | 1 | Số liệu trong lời đọc/overlay có trong brief hoặc giả định rõ | `unsupported_numbers` | — |
| `originality` | 1 | Chống sao chép lời đọc video mẫu (Style Learner) | `originality` | Retry riêng cảnh |
| `schema_basic` | 1 | JSON/schema cơ bản không sửa được | `structure_notes` | — |
| `ai_prompt` | 2 | Chuẩn hóa prompt AI trước khi cho gọi gateway | `ai_prompt` | `fix_ai_prompt` |
| `attribution` | 2 | Định dạng nguồn Theo ... | `attribution` | `fix_attribution` |
| `brief_binding` | 2 | Cập nhật metadata brief và kiểm tra lại | `freshness` | `rebind` |
| `broll_query` | 2 | Query stock hợp lệ và khác nhau | `structure_notes` | — |
| `duration` | 2 | Căn tổng thời lượng bằng code | `duration` | `fix_duration` |
| `fact_reuse` | 2 | Giảm lặp ID, ưu tiên fact tương đương | `repeated` | `fix_repeated` |
| `format` | 2 | Đồng bộ format | `format_issues` | `fix_format` |
| `open_loop` | 2 | Gán fact payoff liên quan hoặc bỏ câu hỏi | `open_loop` | `fix_open_loop` |
| `outline_structure` | 2 | Đồng bộ dàn ý/blueprint | `outline_shape` | `fix_outline_shape` |
| `shot_structure` | 2 | Chuẩn hóa mảng/shot/role/schema trình bày | `structure_notes` | — |
| `title` | 2 | Tiêu đề cấp video hợp lệ | `title` | `fix_title` |
| `audit_clarity` | 3 | Audit không giải thích kết luận | `structure_notes` | — |
| `cliches` | 3 | Cụm sáo rỗng | `check` | — |
| `ending_style` | 3 | Kết video đúng kiểu | `check` | — |
| `examples` | 3 | Thiếu ví dụ/số liệu cụ thể | `depth` | — |
| `hook_length` | 3 | Độ dài hook | `check` | — |
| `hook_strength` | 3 | Hook hấp dẫn/cách mở | `check` | — |
| `open_loop_clarity` | 3 | Câu hỏi mở không rõ | `unclear_loop` | — |
| `overlay_style` | 3 | Độ dài/ý nghĩa overlay | `check` | — |
| `pattern_interrupt` | 3 | Thiếu pattern interrupt | `check` | — |
| `repeated_ideas` | 3 | Lặp lời/ý | `check` | — |
| `scene_target` | 3 | Số cảnh dưới mục tiêu | `thin_scenes` | — |
| `sentence_length` | 3 | Câu dài/cấu trúc câu | `check` | — |
| `transitions` | 3 | Chuyển ý/mở cảnh bị lặp | `check` | — |
| `tts_format` | 3 | Cách đọc số/đơn vị/viết tắt | `check` | — |
| `word_budget` | 3 | Lượng từ lệch quá khoảng ±20% | `check` | — |

## Cấu hình

Sửa `config/validation.yaml`, ví dụ:

```yaml
rules:
  cliches:
    group: 1
```

Khi nâng cảnh báo lên nhóm 1, lỗi đó được retry riêng cảnh; nếu vẫn lỗi sẽ lưu bản nháp. Các sửa cấu trúc được chạy trước kiểm tra và không gọi Gemini. JSON không thể parse/type-check vẫn cần schema cơ bản để pipeline có đối tượng hợp lệ; hạ nhóm trong YAML không thể biến JSON hỏng thành EditPlan. File cấu hình sai ID/nhóm được báo rõ, không âm thầm bỏ qua. Cache Director bao gồm chính sách đang dùng.

## Trình tự và dữ liệu kiểm tra

1. Ngay sau JSON Gemini: `normalize_plan_structure` căn các mảng theo shot, tạo shot thiếu, làm sạch/biến thể query stock. Không gọi Gemini để sửa query.
2. Parse schema cơ bản; khi lỗi có vị trí cảnh, chỉ yêu cầu JSON sửa cảnh đó và giữ các cảnh khác.
3. Chạy bảng RULES: dàn ý/open loop → kiểm chứng fact/số/tên/trích dẫn → tự sửa trình bày → cảnh báo văn phong.
4. Nhận xét từ audit Gemini cũng đi qua bảng nhóm; audit chê văn phong không kích hoạt retry. Chỉ lỗi nhóm 1 có cảnh cụ thể mới được sửa lại cảnh đó.
5. Gộp cảnh để giảm fact lặp được hoãn tới sau audit, tránh đổi ID làm retry sai cảnh. Chỉ đổi sang fact có nội dung tương đương; không gắn fact khác nghĩa để lách luật.
6. Người hóa lỗi thì dùng lời đọc lượt 2 đã kiểm tra, khi bản đó không có lỗi căn cứ đã biết. Nếu vẫn còn lỗi nhóm 1, giữ bản nháp và ghi chính xác cảnh/ID luật.

`validation_events` lưu scene_id, rule_id, group, action, phase, message; review_notes giữ bản dễ đọc. Trang Edit Plan hiển thị bảng và cho sửa bản nháp. report.md liệt kê cả tự sửa/cảnh báo và lỗi cần sửa. Log UTF-8 ở logs/director_errors.log.

Số liệu lời đọc/overlay phải có trong brief hoặc nằm trong câu giả định được đánh dấu rõ; ngoại lệ giả định chỉ áp dụng từng câu. Tên riêng/trích dẫn được kiểm tra bằng code và audit ngữ nghĩa. Các kiểm tra này không thay thế đối chiếu nguồn trong Researcher.

## Hồi quy dự án thật

Kiểm tra cả output đang có và snapshot của bốn dự án được yêu cầu. Hai bản nháp auto-cong-nghe-ace8ccb3 và auto-cong-nghe-47d6390a lưu `plan: null`: không còn kịch bản gốc để validate nguyên trạng. Test dùng lỗi đã lưu, brief và cấu hình thật để tái dựng cấu trúc đầu vào và kiểm tra lại query/open loop; không tuyên bố đã khôi phục lời đọc cũ. Các file output gốc được giữ nguyên.

## Phạm vi lỗi ngoài văn phong

Lỗi API/kết nối, thiếu file nguồn, khóa project, thiếu audio, đường dẫn không an toàn và hạn mức chi phí là lỗi vận hành riêng; không hạ thành cảnh báo chất lượng để chạy bằng dữ liệu hỏng.
