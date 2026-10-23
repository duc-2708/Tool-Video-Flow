# Học phong cách từ video mẫu

## Upload Unicode, phản hồi thô và giới hạn Gemini

Cập nhật xử lý HTTP 400, schema phẳng, giới hạn đoạn video và chính sách giữ nguyên raw: xem [style_gemini_compatibility.md](style_gemini_compatibility.md). Phần cập nhật này thay thế hướng dẫn Học lại/tự thử lại raw cũ bên dưới: đã có `.raw.txt` thì chỉ parse tại máy, kể cả Học lại; không tự gọi Gemini vì raw bị cắt. Mặc định output mới là 8192 token, không còn 16000.

Tên file tiếng Việt, dấu nháy cong và `#` được giữ trong JSON/SQLite. Khi upload, ứng dụng mở stream nhị phân với tên/display name `<SHA256>.mp4` ASCII. Không đưa basename gốc vào header HTTP của SDK; stream được đóng sau upload và luôn yêu cầu xóa file Gemini khi xử lý xong hoặc lỗi.

Trước parse/validate, phản hồi Gemini được ghi UTF-8, flush/fsync qua atomic I/O vào `assets/reference_videos/analysis/<category_id>/<SHA256>.raw.txt` (mẫu chưa phân loại dùng `_unsorted`). `.raw.meta.json` giữ nguồn gốc và trạng thái phản hồi. Token bị cắt hoặc JSON lỗi vẫn giữ bản thô. Bản thô đầy đủ được parse lại tại máy, lỗi schema không tự gọi Gemini. Riêng `MAX_TOKENS` hoặc JSON chưa cân bằng được đánh dấu `truncated=true`: lệnh phân tích thường thử thêm đúng một lần với prompt gọn, tối đa 12 cảnh, mỗi mô tả tối đa 20 từ. Bản thô và metadata cũ được lưu với hậu tố hash; nếu lần gọn vẫn lỗi, lần chạy sau không tự tạo thêm request. Muốn thử mới phải chủ động Học lại. Parser chịu code fence, chữ trước/sau JSON, dấu phẩy cuối và dấu nháy đơn/nháy cong đơn giản; không dựng phần JSON bị cắt. Nội dung key nếu vô tình có trong output vẫn được che trước khi lưu.

Mỗi cảnh chỉ bắt buộc `start_sec`, `end_sec`, `purpose`. Các quan sát như số shot/số từ, màu sắc, hiệu ứng, nhạc, ngôi xưng, kết/CTA dùng mặc định hoặc `null` khi thiếu, không bịa số đếm. Chuỗi số, danh sách thay chuỗi và mô tả chuyển cảnh được chuẩn hóa; `transition_to_next` cảnh cuối luôn `null`. Cảnh đảo mốc hoặc chồng lấn vẫn bị từ chối. Nếu timeline dài hơn thời lượng video, ứng dụng co đều các mốc, ghi rõ đây là ước lượng cần đối chiếu trong cảnh báo; bản thô giữ nguyên. Lỗi hiển thị chính xác đường dẫn trường (ví dụ `scenes.0.end_sec`). Phản hồi bị Gemini chặn an toàn không được đưa vào hồ sơ.

Trong **Phong cách mẫu**, mở **Sửa lại từ bản thô** bên dưới phần phân tích: sửa JSON/trường sai, bấm nút cùng tên để lưu và validate tại máy. Không yêu cầu API key cho việc sửa bản thô. Bản trước khi sửa được lưu cạnh file chính với hậu tố hash. CLI cũng có chế độ chỉ sửa/parse, không thể gọi Gemini:

```powershell
.\.venv\Scripts\python.exe -m pipeline.style_learner --category "tin tức" --analyze --from-raw
```

Nếu chưa có bản thô cho một file, `--from-raw` báo riêng file đó rồi tiếp tục file khác. Sửa raw ngoài ứng dụng cũng được; dùng `--from-raw` để cập nhật cache kể cả khi trước đó đã có JSON hợp lệ. Ghi chú/model/cấu hình đổi không làm tự gọi lại một video đã có raw; bản phân tích giữ nguồn gốc của lần gọi trước. Muốn tạo phản hồi mới, dùng **Học lại** có xác nhận chi phí. Bản thô cũ được giữ lại trước khi thay.

Các mặc định mới nằm trong `.env.example`; không cần sửa `.env` để có hiệu lực:

| Biến | Mặc định | Ý nghĩa |
|---|---:|---|
| STYLE_MEDIA_RESOLUTION | low | `low` hoặc `medium`, truyền vào GenerateContentConfig |
| STYLE_MAX_OUTPUT_TOKENS | 16000 | Ngân sách đầu ra; lần gọn vẫn dùng cùng ngân sách |
| STYLE_VIDEO_FPS | 0.5 | Lấy mẫu khung hình, (0, 1] FPS |
| STYLE_TPM_LIMIT | 250000 | Ngân sách token đầu vào ước lượng trong cửa sổ 60 giây |
| STYLE_RPM_LIMIT | 2 | Giới hạn request thử/phút; chỉnh theo gói thực tế |
| STYLE_REQUEST_INTERVAL_SEC | 5 | Khoảng cách tối thiểu giữa hai lần request |

Style Learner xử lý tuần tự. Ledger `.cache/style_rate_limit.json` dùng file lock để chia sẻ giới hạn giữa CLI/UI và các tiến trình; mỗi retry/fallback cũng đặt trước ngân sách. Khi cần chờ, UI/CLI hiện thời gian; lỗi 429/503/504 vẫn dùng backoff chung. Nếu một video ước lượng vượt ngân sách/phút thì dừng trước request, hướng dẫn giảm FPS/resolution hoặc cắt video.

Ước lượng mới: `(64 × FPS + 40) token/giây` với low, `(256 × FPS + 40)` với medium, cộng prompt. Đây là ước lượng lập kế hoạch, không phải số liệu billing; token thực còn phụ thuộc model. FPS thấp có thể bỏ lỡ các shot/chữ rất ngắn; tăng FPS/medium khi cần quan sát kỹ, vẫn chịu ngân sách. [Tài liệu Gemini về video và lấy mẫu khung hình](https://ai.google.dev/gemini-api/docs/video-understanding), [độ phân giải media](https://ai.google.dev/gemini-api/docs/media-resolution).

Quét kênh/từ khóa YouTube qua API chính thức và học trực tiếp URL: xem [hướng dẫn quét YouTube](youtube_style_scan.md). Kết quả gộp vào cùng hồ sơ danh mục với MP4 local; không tải video của bên thứ ba.

## Hồ sơ theo danh mục và phân cảnh chi tiết

`config/categories.yaml` có ID ổn định, ví dụ `tin-tuc`, `cong-nghe`, `thoi-trang`, `giai-tri`, `kinh-doanh`, `suc-khoe-doi-song`, `the-thao`, `du-lich`, `game`. CLI nhận cả ID và tên tiếng Việt. Giữ ID ổn định khi chỉ đổi tên hiển thị.

```text
assets/reference_videos/
  cong-nghe/a.mp4
  cong-nghe/a.txt                 # ghi chú tùy chọn
  du-lich/b.mp4
  _unsorted/c.mp4                 # cần xác nhận danh mục
  old-sample.mp4                  # cũng là chưa phân loại
  analysis/cong-nghe/a.json       # không trùng với a.mp4 ở danh mục khác
  analysis/.cache/<hash>.json
config/style_profiles/
  _default.json                  # hồ sơ chung, 0 video làm cơ sở
  cong-nghe.json                 # tất cả mẫu hợp lệ trong danh mục
  cong-nghe.news.json            # hồ sơ theo type khi có mẫu tương ứng
  cong-nghe.review.json
```

Trang **Phong cách mẫu** có tab cho từng danh mục, **Chưa phân loại** và **Preset tự chọn** (giữ cách dùng preset cũ). Tab chỉ xử lý danh mục đang mở, tránh đọc toàn bộ thư viện mỗi lần rerun.

1. Thêm MP4 bằng upload hoặc đặt file vào thư mục. Upload chỉ lưu local; chưa gọi Gemini. File trùng tên bị từ chối, không ghi đè.
2. Xem ước lượng và xác nhận trước khi **Phân tích**. `STYLE_MAX_VIDEOS_PER_RUN` vẫn giới hạn mỗi lô. Cache dùng hash video/ghi chú/model/prompt, nên cùng nội dung sau khi chuyển thư mục vẫn dùng cache.
3. Video ở root/`_unsorted` có `category_guess` và confidence. Chọn lại danh mục nếu cần, bấm **Xác nhận và chuyển file**; video, ghi chú và phân tích được chuyển cùng nhau. Gemini không tự chuyển file.
4. Xem bảng `scenes[]`: mốc start/end, mục đích, tóm tắt lời đọc, số từ/tốc độ, số shot, hiệu ứng và câu nối dạng khuôn. Mốc đảo hoặc chồng lấn bị từ chối riêng file đó; scene_count/avg_scene_sec không khớp được tính lại kèm ghi chú. Trường phụ có thể thiếu; cảnh báo chuẩn hóa nằm dưới từng video.
5. Hồ sơ được tự tổng hợp lại tại máy khi thêm/xóa/đổi video hoặc phân tích. Video mới chưa phân tích chỉ được đánh dấu chờ; không tự upload và không tính vào mẫu làm cơ sở. Có nút **Tổng hợp lại** để làm mới ngay. Cùng hash chỉ tính một mẫu: 1 = yếu, 2 = đang tích lũy, từ 3 = ổn.
6. Hồ sơ chứa bảng 30/60/90/120/180 giây (số cảnh, thời gian từng cảnh và min–max), narrative_flow, mẫu cảnh theo thứ tự, khuôn hook, cụm nối xếp theo số video cùng dùng, giọng kể, nhịp và kiểu hình/caption/audio. Bảng số cảnh chỉ dùng những phân tích có `scenes[]` chi tiết; không giả định số phần của phân tích cũ là số cảnh.
7. Sửa quy tắc/cụm nối, đánh dấu **Khóa...**, rồi bấm **Lưu quy tắc và khóa**. Trường đã khóa được giữ qua tự tổng hợp và nút Tổng hợp lại. Muốn học lại trường đó, bỏ khóa rồi lưu trước khi tổng hợp.
8. **So khớp kịch bản** đọc một project đã có edit_plan.json; hiển thị kịch bản bên cạnh cấu trúc hồ sơ, so số cảnh, giây/cảnh, shot/10 giây và số lần dùng cụm nối. Không gọi Gemini hoặc sửa project.

Trong **Tạo video theo danh mục**, **Khám phá chủ đề**, **Tạo video**, chọn danh mục sẽ nạp hồ sơ tự động. Khi có mẫu phù hợp `suggested_type`, ưu tiên hồ sơ `news/review/story`, rồi hồ sơ chung danh mục. Không có mẫu hợp lệ thì dùng `_default.json` và báo **“chưa có video mẫu cho danh mục này”**. Có thể đổi preset hoặc chọn **Không dùng**; CLI dùng `--style-preset none` để tắt rõ ràng.

Director đưa hồ sơ vào cả ba lượt, dùng bảng phân cảnh/nhịp và thứ tự mục đích cảnh; co giãn theo lượng fact, giữ hook và giới hạn shot. `style_purpose` ghi mục đích chi tiết trong JSON bên cạnh role kỹ thuật. Các khuôn nối được biến tấu, lặp quá hai lần là cảnh báo nhóm 3. Các nhóm luật, kiểm chứng fact/source và chống sao chép giữ nguyên. Nội dung/tóm tắt lời đọc của mẫu chỉ dùng để so khớp tại máy, không gửi trong prompt tạo kịch bản.

Các lệnh mới, chạy riêng từng lệnh trong `video_ai_tool`:

```powershell
.\.venv\Scripts\python.exe -m pipeline.style_learner --category "công nghệ" --analyze --estimate-only
```

```powershell
.\.venv\Scripts\python.exe -m pipeline.style_learner --category "công nghệ" --analyze
```

```powershell
.\.venv\Scripts\python.exe -m pipeline.style_profile --category "công nghệ" --rebuild
```

```powershell
.\.venv\Scripts\python.exe -m pipeline.style_profile --category "công nghệ" --type review --rebuild
```

```powershell
.\.venv\Scripts\python.exe -m pipeline.run_all --category "công nghệ" --topic "Một sự kiện cụ thể" --type news --duration 60 --review
```

```powershell
.\.venv\Scripts\python.exe -m pipeline.auto_category --category "công nghệ" --duration 60 --review
```

Hồ sơ và phân tích cũ vẫn đọc được. Prompt phân tích mới có phiên bản/hash mới; muốn có bảng cảnh chi tiết cho mẫu cũ cần chủ động phân tích lại sau khi xem ước lượng. Không tự tạo job có phí khi nâng cấp hoặc mở UI.

Phần dưới giữ hướng dẫn preset tự chọn và cấu hình chung.

Đặt video do bạn lựa chọn trong `assets/reference_videos/`, định dạng `.mp4`. Ghi chú tùy chọn dùng cùng tên, ví dụ `a.mp4` và `a.txt`. Công cụ chỉ phân tích file local; không tải video từ nền tảng khác.

## Dùng trên UI

1. Mở trang **Phong cách mẫu**. Chọn một video để phân tích riêng hoặc chọn nhiều video trong một lô.
2. Xem số video, tổng thời lượng và ước lượng token. Đồng ý upload/dùng quota rồi bấm **Phân tích video đã chọn**. Phân tích chạy trong thread; có thể chuyển trang. UI tự cập nhật trạng thái.
3. Xem hook, cấu trúc, nhịp, quy tắc và JSON của từng file. File lỗi được báo riêng, các file khác vẫn tiếp tục.
4. Chọn/bỏ các video ở **Video đưa vào preset**, đặt tên, bấm **Tổng hợp thành preset**. Sửa quy tắc từng dòng, rồi **Lưu preset**. Tổng hợp không gọi Gemini.
5. Chọn **Phong cách mẫu** trong Tạo video, Tạo video theo danh mục hoặc Edit Plan. Mặc định **Không dùng** giữ luồng hiện có.
6. Edit Plan cho sửa caption (bật/tắt, nhóm chữ, cỡ, màu, vị trí), âm lượng nhạc, ducking và hiệu ứng/overlay từng shot. Các chỉnh sửa được giữ khi lưu và khi viết lại lời đọc. Nếu đổi kế hoạch sau khi đã tạo Assets, chạy lại Assets trước Render để resolved plan nhận thay đổi.

## Chạy local

Từ thư mục `video_ai_tool`, từng lệnh riêng:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

Chỉ ước lượng, không upload hoặc gọi Gemini:

```powershell
.\.venv\Scripts\python.exe -m pipeline.style_learner --analyze-all --estimate-only
```

Bắt đầu phân tích sau khi in ước lượng (lệnh này sử dụng quota):

```powershell
.\.venv\Scripts\python.exe -m pipeline.style_learner --analyze-all
```

```powershell
.\.venv\Scripts\python.exe -m pipeline.style_learner --videos a.mp4
```

```powershell
.\.venv\Scripts\python.exe -m pipeline.style_profile --name "khám phá khoa học" --videos a.mp4 b.mp4
```

```powershell
.\.venv\Scripts\python.exe -m pipeline.run_all --topic "Chủ đề cụ thể" --type news --format tiktok --duration 60 --style-preset "khám phá khoa học" --review
```

```powershell
.\.venv\Scripts\python.exe -m pipeline.auto_category --category "công nghệ" --region both --days 3 --duration 60 --format tiktok --style-preset "khám phá khoa học" --review
```

## Cấu hình và chi phí

Các tên biến mới được ghi trong `.env.example`; code có mặc định nên không cần sửa `.env` hiện có để khởi động:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| GEMINI_STYLE_MODEL | trống → GEMINI_MODEL | Model hỗ trợ video của tài khoản |
| STYLE_MAX_VIDEOS_PER_RUN | 5 | Số video tối đa mỗi lô |
| STYLE_MAX_FILE_MB | 200 | Giới hạn file do ứng dụng đặt |
| STYLE_MAX_DURATION_SEC | 600 | Giới hạn thời lượng do ứng dụng đặt |
| STYLE_TIMEOUT_SEC | 180 | Timeout request và thời gian chờ xử lý file |

Ước lượng đầu vào dùng công thức FPS/resolution ở trên cộng văn bản; đầu ra dự trù `STYLE_MAX_OUTPUT_TOKENS` (mặc định 16000)/video. Đây là ước lượng lập kế hoạch, không phải giá tiền hoặc số token thanh toán. Video có cache/bản thô hợp lệ hoặc dùng `--from-raw` được tính 0 token mới. Bản thô bị cắt chờ thử gọn được tính vào ước lượng có phí; `--from-raw` vẫn chỉ parse tại máy. Retry tạm thời và một lần thử gọn có thể phát sinh thêm token.

## Dữ liệu và chống sao chép

- Prompt `prompts/style_analyze.md` giữ nguyên đoạn yêu cầu phân tích người dùng cung cấp; ghi chú/thời lượng và schema được truyền thêm riêng.
- Kết quả từng video: `assets/reference_videos/analysis/<tên>.json`. Cache bền theo SHA-256 video + ghi chú + model + prompt + phiên bản; file đổi tên nhưng cùng nội dung không bị phân tích lại. Có lock chống hai worker upload cùng một nội dung.
- File upload được xóa trong `finally`, kể cả khi Gemini/JSON lỗi. Nếu xóa thất bại sau retry, ID file và cảnh báo được lưu vào trạng thái/log; kết quả đã phân tích vẫn được cache để tránh trả phí lại chỉ vì lỗi dọn file.
- Preset có tên: `config/style_presets/<slug>.json`; bản vừa lưu cũng được ghi vào `config/style_profile.json`. Quy tắc trùng được loại theo từng video rồi xếp theo số video cùng có quy tắc đó. Bản sao video cùng hash không tăng số phiếu.
- Kế hoạch giữ snapshot preset để Assets/Render/resume nhất quán. `style_profile.reference_texts` là tóm lược lời đọc dùng so khớp tại máy, bị loại khỏi mọi prompt Director/audit. Facts và nguồn vẫn lấy từ brief.
- Hook/structure/nhịp/giọng chỉ hướng dẫn cách kể. Số cảnh chịu giới hạn dữ liệu/thời lượng; shot vẫn 1.5–4 giây và Assets căn theo audio thật. Không clone giọng; TTS vẫn dùng giọng được chọn. Font mô tả không được coi là nhận diện font chính xác; renderer dùng font local hiện có.
- Chống sao chép so n-gram bốn từ và tương đồng câu, bỏ qua câu quá ngắn (dưới bảy từ). Trên 60% kích hoạt luật `originality`, chỉ retry cảnh bị trùng. Nếu vẫn trùng sau giới hạn retry, lưu draft thay vì xuất nội dung đó. Transcript chỉ là outline/tóm lược nên đây là biện pháp phát hiện hỗ trợ, không phải đảm bảo phát hiện mọi sao chép từ toàn bộ lời nói gốc.
- Không trích, sao chép hay dùng hình/âm thanh video mẫu trong sản phẩm. Editor vẫn chỉ đọc audio/clip của project và nhạc/SFX trong thư mục assets tương ứng.
- Lỗi UTF-8: `logs/style_learner_errors.log`; key được che qua Diagnostics. Các file video mẫu/analysis được bỏ qua khi commit.

Tích hợp theo [Gemini video understanding](https://ai.google.dev/gemini-api/docs/video-understanding) và [Files API](https://ai.google.dev/api/files), dùng SDK đã cài trong dự án, không hardcode tên model.

## Phục hồi trường phụ từ bản thô, không tốn thêm token

```powershell
.\.venv\Scripts\python.exe -m pipeline.style_learner --category "công nghệ" --analyze --from-raw --max-sec 180
```

- Màu `#RGB`, `#RRGGBB`, tên màu tiếng Việt/Anh được chuẩn hóa về hex. Mô tả gần đúng như “vàng chanh”, “xanh nhạt” dùng màu cơ bản gần nhất; mô tả gốc lưu trong `captions.color_note`. Màu không nhận ra lưu `null`; renderer/UI dùng màu mặc định khi cần.
- Mốc cảnh và transcript được sắp xếp, cắt tại thời lượng video thật/giới hạn đoạn phân tích. `end_sec` sai được suy từ cảnh tiếp theo hoặc độ dài trung bình; mục không thể phục hồi bị loại, có ghi rõ lý do. Không co giãn toàn bộ timeline để ép khớp.
- Font, vị trí, âm thanh và các quan sát phụ sai kiểu/ngoài phạm vi dùng default hoặc `null`, không làm hỏng bản phân tích. Cần còn ít nhất một cảnh hợp lệ; hook/structure thiếu được suy từ purpose của các cảnh quan sát được, không bịa nội dung.
- Chi tiết lưu trong `analysis.analysis_warnings` và gộp vào `warnings` của bản ghi. UI **Phong cách mẫu → danh mục → Phân tích kịch bản/phân cảnh** hiển thị số lượng và nội dung cảnh báo, nhãn `done (có cảnh báo)`. DB vẫn dùng trạng thái máy `done` để hồ sơ được tổng hợp bình thường.
- `--from-raw` giữ nguyên `.raw.txt`, không upload/call Gemini. Nếu JSON bị cắt chưa cân bằng, chỉ báo lỗi và giữ dữ liệu; không tự tạo phần còn thiếu.
