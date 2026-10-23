# Quét YouTube để học phong cách theo danh mục

Luồng này chỉ gọi YouTube Data API v3 để lấy metadata và gửi **URL công khai** tới Gemini. Không tải video/audio, không lấy transcript, không scrape trang web hay nền tảng khác. Chỉ học phong cách, không sao chép nội dung. Assets/Render không dùng hình hoặc âm thanh từ các URL mẫu.

## Dùng trên UI

1. Mở **Phong cách mẫu**, chọn tab danh mục, mở khu **Nguồn quét YouTube**.
2. Chọn loại nguồn **Kênh/link YouTube** hoặc **Từ khóa**, nhập giá trị, bấm **Thêm nguồn**. Link watch/youtu.be/shorts được quy về kênh đăng. `@handle` và `/channel/UC...` phân giải trực tiếp. Link playlist được quy về kênh sở hữu, sau đó quét uploads của kênh (không quét các kênh khác có mặt trong playlist). Tên kênh luôn hiện danh sách để bạn chọn/xác nhận, kể cả chỉ tìm được một kết quả. Không tự chọn.
3. Bật nguồn, chọn giới hạn và bấm **Quét nguồn này** hoặc **Quét tất cả nguồn của danh mục**. Quét metadata chạy nền; chưa gọi Gemini. Nguồn lỗi được ghi rõ, nguồn khác vẫn tiếp tục.
4. Đọc bảng video mới/đã học/bị bỏ qua. Bỏ chọn các video không muốn học. Bảng ước lượng cập nhật theo phần đã chọn. Tick xác nhận chi phí và bấm **Xác nhận học video đã chọn**. Giá thực tế phụ thuộc model/gói Gemini; số token là ước lượng bảo thủ.
5. Xem kết quả từng video. Video lỗi được ghi riêng; chọn **Thử lại video lỗi** để đưa vào một lượt xác nhận mới. **Học lại** cũng chỉ chuẩn bị lượt xác nhận, không tự gọi API; bản phân tích tốt cũ được giữ nếu lần học lại lỗi. **Bỏ qua mãi mãi** lưu dấu trong SQLite và loại video khỏi hồ sơ phong cách. Không xóa file mẫu local.
6. Sau video mới thành công, hồ sơ chung và các hồ sơ `news/review/story` được tổng hợp tại máy, giữ các trường bạn đã khóa. Director vẫn dùng các luật fact/nguồn/chống sao chép cũ; dữ liệu mẫu không trở thành facts.

YouTube Data API công khai **không có cờ `isShort` chính xác**, cũng không cung cấp tỷ lệ khung hình công khai đủ tin cậy để xác định. Bộ lọc UI ghi rõ **ước lượng theo thời lượng**: `shorts` = ≤180 giây, `regular` = >180 giây. Không nhận diện chắc chắn Shorts. Muốn học video dài, tăng `SCAN_MAX_VIDEO_SEC` trên 180.

## Cấu hình

Không cần thay đổi `.env` để có các giá trị mặc định mới. Các tên cấu hình cũng có trong `.env.example`:

| Biến | Mặc định | Ý nghĩa |
|---|---:|---|
| SCAN_MAX_NEW_VIDEOS | 5 | Tổng số video mới tối đa trong một lô (không nhân theo số nguồn) |
| SCAN_MAX_VIDEO_SEC | 180 | Thời lượng tối đa |
| SCAN_MAX_AGE_DAYS | 180 | Tuổi video tối đa khi quét |

Vẫn cần `YOUTUBE_API_KEY` để quét, `GEMINI_API_KEY` và `GEMINI_STYLE_MODEL` (trống thì dùng `GEMINI_MODEL`) để học. Không hiển thị giá trị key. Giới hạn lô còn chịu `STYLE_MAX_VIDEOS_PER_RUN`. Retry 429/503/504 dùng backoff/timeout Gemini hiện có; một video không đạt không làm hỏng lô.

Quota YouTube dùng chung ledger với Research/Trends tại `.cache/youtube_quota.json`: search=100, các list khác=1 mỗi lần HTTP thử, kể cả retry. Chặn trước request nếu vượt `YOUTUBE_DAILY_QUOTA` hoặc giới hạn search mỗi run. Quét từ khóa còn chặn số search/ngày theo `YOUTUBE_MAX_SEARCHES_PER_RUN` (tính cả search đã dùng trong ledger chung). Quota là ước lượng tại máy, ngày theo Pacific của YouTube; Gemini Style hiển thị số lần request thử tại ứng dụng trong ngày UTC, gồm retry và fallback, không phải số liệu billing của Google. Không tự reset ledger để né quota.

Kênh dùng `channels.list(contentDetails)` → `playlistItems.list` → `videos.list`, không mất 100 đơn vị search cho mỗi kênh. Dừng phân trang tại video đã ghi nhận hoặc đủ giới hạn; tối đa 20 trang/nguồn để tránh quét không giới hạn. Keyword dùng `search.list(type=video, order=date/viewCount)`.

## SQLite và JSON

- `data/app.db`: SQLite chuẩn, WAL, busy timeout, mỗi thao tác mở/đóng kết nối riêng. `user_id` mặc định 1; không giữ kết nối trong thread/session.
- `scan_sources`: nguồn quét, trạng thái bật/tắt và lần quét cuối.
- `learned_videos`: UNIQUE(platform, video_id, category_id), trạng thái done/failed/skipped, lỗi đã che key, đường dẫn phân tích, cờ bỏ qua vĩnh viễn.
- `learned_video_sources`: liên kết một video với nhiều nguồn quét, phục vụ lọc UI mà không học trùng.
- `api_usage`: đếm request Gemini Style từ ứng dụng, không lưu key/nội dung request.
- JSON YouTube: `assets/reference_videos/analysis/<category_id>/<video_id>.json`, dùng cùng `AnalysisRecord/StyleAnalysis/scenes[]` như local. Chỉ đánh dấu done sau khi ghi và đọc kiểm tra JSON thành công.
- Local MP4: `platform=local`, `video_id=SHA256(file)`. Phân tích mới hoặc tổng hợp hồ sơ sẽ nhập phân tích local còn hiệu lực vào SQLite; cache hash/prompt/model cũ vẫn dùng. Không tự phân tích lại mẫu cũ khi mở UI.
- Hồ sơ `config/style_profiles/<category_id>.json` gộp mẫu local còn tồn tại và YouTube done. Thêm mẫu mới chỉ tổng hợp lại, không gọi Gemini cho mẫu đã học. Tham chiếu lời đọc/tóm tắt vẫn giữ riêng để kiểm tra chống sao chép, không đưa vào guidance viết kịch bản.

## CLI — chạy từng lệnh trong `video_ai_tool`

Thêm kênh bằng handle:

```powershell
.\.venv\Scripts\python.exe -m pipeline.scan_sources --category "công nghệ" --add "https://www.youtube.com/@TEN_KENH"
```

Tìm theo tên: hiện danh sách, cần chọn channel_id trên terminal; khi chạy không tương tác, chạy lại kèm `--choose UC...`. `--yes` không tự chọn kênh.

```powershell
.\.venv\Scripts\python.exe -m pipeline.scan_sources --category "công nghệ" --add "Tên kênh"
```

Thêm từ khóa:

```powershell
.\.venv\Scripts\python.exe -m pipeline.scan_sources --category "công nghệ" --kind keyword --add "AI technology"
```

Quét, xem bảng/ước lượng rồi trả lời `y` nếu muốn học. Khi stdin không tương tác, mặc định dừng ở preview:

```powershell
.\.venv\Scripts\python.exe -m pipeline.scan_sources --category "công nghệ" --scan --max 5
```

Cho phép Gemini ngay sau khi in preview/ước lượng:

```powershell
.\.venv\Scripts\python.exe -m pipeline.scan_sources --category "công nghệ" --scan --source 1 --max 5 --yes
```

Thử lại video lỗi (vẫn cần xác nhận hoặc `--yes`):

```powershell
.\.venv\Scripts\python.exe -m pipeline.scan_sources --category "công nghệ" --retry-failed --max 5
```

Nguồn kỹ thuật chính thức: [Gemini YouTube URL input](https://ai.google.dev/gemini-api/docs/video-understanding), [channels.list](https://developers.google.com/youtube/data/reference/rest/v3/channels/list), [playlistItems.list](https://developers.google.com/youtube/data/reference/rest/v3/playlistItems/list), [videos resource](https://developers.google.com/youtube/data/reference/rest/v3/videos).
