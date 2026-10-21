# Học phong cách từ video mẫu

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

Ước lượng token đầu vào dùng thời lượng × 400 cộng phần văn bản; đầu ra dự trù 8192/video. Đây là ước lượng lập kế hoạch, không phải giá tiền hoặc số token thanh toán. Sampling/model/âm thanh có thể làm kết quả thực tế khác. Video có cache hợp lệ được tính 0 token mới. Retry lỗi tạm thời/output có thể phát sinh thêm token; không có cam kết mức phí cố định.

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
