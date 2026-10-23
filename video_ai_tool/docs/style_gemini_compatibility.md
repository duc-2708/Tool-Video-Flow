# Style Learner: cấu hình Gemini và phạm vi phân tích

Gemini trả HTTP 400 `INVALID_ARGUMENT / Request contains an invalid argument.` không đồng nghĩa file video hỏng. Log cũ chỉ có thông báo chung nên không đủ bằng chứng kết luận tham số nào sai. Phiên bản mới ghi cấu hình thực tế của từng request và phản hồi lỗi đầy đủ vào `logs/style_learner_errors.log` bằng UTF-8 sau khi che key: model, output tokens, độ phân giải, MIME JSON, hai cờ response_schema/response_json_schema, kích thước schema/prompt, thinking config, kích thước/MIME/thời lượng video, FPS và start/end offset. Log không chứa header xác thực, nội dung `.env`, URI Files API hoặc prompt gốc.

Schema wire của Style được tách khỏi Pydantic: inline tham chiếu, bỏ Union/null và additionalProperties. Các trường phụ có thể bỏ qua; parser/before-validator Pydantic vẫn xử lý null, chuỗi/dict và dữ liệu lệch kiểu ở phía local. Schema đầy đủ cũ khoảng 10061 ký tự, bản phẳng hiện khoảng 4589; bản gọn khoảng 877, không có anyOf/$ref/$defs/additionalProperties. Không thay schema của Researcher/Director.

Chỉ với Style, sau 400 sẽ thử mỗi cấu hình thay thế tối đa một lần, cộng dồn thay đổi theo thứ tự:

1. Bỏ media_resolution.
2. Bỏ response_json_schema, giữ application/json, thêm schema phẳng vào prompt.
3. Chuyển prompt gọn tối đa 12 cảnh, output 8192 token.
4. Bật lại structured output bằng schema thiết yếu phẳng (start_sec, end_sec, purpose).

Bỏ qua bước đã trùng cấu hình hiện tại. 401/403/404 không bisect; lỗi tạm thời vẫn qua bộ backoff chung và bộ đếm quota/rate limiter trước mỗi request. Không lặp lại yêu cầu 400 với cùng cấu hình. Request được chấp nhận được ghi nhớ tại `.cache/style_compatibility.json` theo model/SDK/cấu hình đầu vào và dùng cho video kế tiếp, kể cả sau khi mở app lại. JSON đầu ra vẫn phải parse/validate riêng; ghi nhớ tương thích HTTP không đồng nghĩa phê duyệt mọi nội dung.

Cấu hình gợi ý chỉ gồm các biến STYLE an toàn nằm trong `logs/style_compatibility.suggested.env`. Đây là file gợi ý mới, không sửa `.env` thật. Người dùng có thể áp dụng các dòng sau khi kiểm tra; nếu chưa chạy API thật thì chưa có kết luận cấu hình nào thành công, test mock không tạo cache/gợi ý thật.

Mặc định mới trong `.env.example`:

```dotenv
STYLE_MAX_OUTPUT_TOKENS=8192
STYLE_MEDIA_RESOLUTION=low
STYLE_USE_RESPONSE_SCHEMA=true
STYLE_SCHEMA_MODE=flat
STYLE_COMPACT_OUTPUT=false
STYLE_MAX_VIDEO_SEC=180
```

`STYLE_MEDIA_RESOLUTION=none` có nghĩa không gửi tham số này; schema_mode nhận flat/essential. Các tùy chọn khác giữ như trước.

Video tối đa 600 giây có thể phân tích đoạn đầu, mặc định 0–180 giây: request dùng VideoMetadata.start_offset/end_offset, không cắt hay sửa file gốc. Ước lượng token dựa trên đoạn này. Kết quả và UI ghi rõ phạm vi đã phân tích, không giả vờ đã xem phần còn lại. Video trên 600 giây được bỏ qua có lý do trong log/UI, không upload/gọi Gemini. Giới hạn dung lượng upload vẫn có hiệu lực; offset không làm giảm kích thước file upload. Có thể dùng --max-sec N, hoặc ô giới hạn giây trên UI, tối đa 600.

```powershell
.\.venv\Scripts\python.exe -m pipeline.style_learner --category "công nghệ" --analyze --max-sec 180 --estimate-only
```

```powershell
.\.venv\Scripts\python.exe -m pipeline.style_learner --category "công nghệ" --analyze --max-sec 180
```

Đã có raw trước lần chạy: không gọi lại Gemini, không ghi đè raw, kể cả force/Học lại. Raw hợp lệ chỉ parse lại; raw lỗi hoặc bị cắt báo để sửa tại máy. Một phản hồi mới bị cắt trong lượt đang chạy vẫn giữ cơ chế thử gọn một lần và lưu archive, nhưng lần chạy kế tiếp không tự tạo request mới. `--from-raw` tuyệt đối không gọi API.
