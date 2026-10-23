<!-- file: README.md -->
# video_ai_tool

## Motion graphics — giai đoạn 1 (tùy chọn)

Renderer HTML local hỗ trợ `hook_card`, `steps_list`, `compare_bars`, nền tối và
phụ đề cụm 2–4 từ. Không lấy hình/mascot từ video mẫu. Các mẫu khác vẫn dùng
Pillow/MoviePy. Luật kiểm chứng và prompt nội dung Director giữ nguyên.

Chạy từng lệnh trong thư mục `video_ai_tool`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

Chỉnh bằng editor trong `.env` (không chứa khóa trong ví dụ này):

```dotenv
MOTION_ENABLED=true
MOTION_FPS=30
MOTION_SCALE=0.5
```

`MOTION_ENABLED=false` mặc định giữ nguyên renderer cũ (preview 540×960/15fps).
Khi bật, scale 0.5 = 540×960, scale 1.0 = 1080×1920 (YouTube xoay ngang),
FPS do MOTION_FPS quyết định cho cả preview/final; chất lượng mã hóa vẫn theo mode.
Thiếu Playwright/Chromium hoặc motion lỗi → cảnh đó dùng đồ họa Pillow và ghi cảnh báo.
Không cần cài FFmpeg riêng. Khởi động lại Streamlit sau khi đổi cấu hình.

```powershell
.\.venv\Scripts\python.exe -m editor.render output/auto-cong-nghe-01bfaa5f/edit_plan.resolved.json --mode preview
```

Render qua UI vẫn chạy worker, hiển thị tiến độ từng cảnh/khung và ETA ước tính.
Cache trong `output/<project>/render/motion_cache/`; đổi dữ liệu/timing/font/engine
thì tự vô hiệu cache. Muốn render lại khi pipeline đã done, dùng trang Render;
không sửa hash/status trong run_state để ép resume.

Demo/benchmark 10s chỉ dùng media local, không gọi API, không sửa project gốc:

```powershell
.\.venv\Scripts\python.exe -m pipeline.motion_demo output/auto-cong-nghe-01bfaa5f/edit_plan.resolved.json --scene 1
```

MP4, ảnh và `benchmark.json` nằm trong `output/motion_demo/`. Audio cảnh gốc được
cắt/pad im lặng tới 10s; đây là phép thử đồ họa, không phải kịch bản mới dài 10s.
Chi tiết timing, beats, cache và giới hạn: [quy trình](../docs/PROCESS.md#71-motion-graphics-html--giai-đoạn-1).

## Chạy test độc lập với cấu hình máy

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp -p no:cacheprovider
```

## AI Video — Veo / Seedance qua gateway

Trang **AI Video** dùng `https://api.buihuuthang.com/v1/videos` (khác API chat/Gemini). Cấu hình `GATEWAY_API_KEY`, `GATEWAY_BASE_URL`, `GATEWAY_VIDEO_MODEL` trong `.env`; sidebar chỉ hiển thị trạng thái đã có/chưa có key. Mặc định Veo 3.1, 4 giây, dọc 9:16, 720p. Có thể chọn Veo 6/8 giây, 1080p hoặc model `seedance-2.5-30s` (giữ các lựa chọn thời lượng Seedance hiện có). `GATEWAY_ALLOWED_MODELS=veo-3.1,seedance-2.5-30s` giới hạn danh sách model trên UI và trước khi gửi POST (cũng nhận JSON array). ID cũ `seedance-2.5` không được tự đổi sang model mới. HTTP 403 hiển thị lỗi gốc đã che key và hướng dẫn kiểm tra quyền model trên dashboard.

Chạy UI local như trên → chọn project → **AI Video** → nhập mô tả → **Tạo 1 clip**. Nút có hiển thị giá tham khảo và gửi một POST có tính phí khi bấm. Chức năng **Kiểm tra kết nối và model** chỉ GET danh sách, không tạo clip. Danh sách model là catalogue; quyền sử dụng và gói/chi phí thực tế do gateway quyết định.

Luồng: `POST /v1/videos` → lưu ID → `GET /v1/videos/{id}?model=...` mỗi 5 giây → `GET /v1/videos/{id}/content?model=...`. Bắt buộc mang đúng model lúc tra/tải, đặc biệt với Veo. Worker chạy nền; có thể đổi trang. Job lưu `output/<project>/ai_video/<hash>.json`, MP4 lưu `clips/ai_<hash>.mp4`, credits riêng trong `ai_video/`. Giữ nguyên edit plan, Assets manifest, audio và credits gốc; clip AI hiện được xem/tải riêng, chưa tự thay b-roll đã chọn trong manifest.

POST không tự retry. Nếu timeout/HTTP 5xx/mất phản hồi, job chuyển sang trạng thái chưa rõ và chặn gửi lại cùng yêu cầu; lấy ID ở dashboard rồi dùng **Tiếp tục bằng Job ID**. Job đã có ID có thể **Tiếp tục kiểm tra / tải clip** sau khi đóng/mở app, thao tác này không tạo job mới. Cùng prompt/tham số được dùng lại từ job cũ; đổi prompt để tạo clip khác. Lỗi gốc đã che key nằm trong `logs/gateway_video_errors.log`.

CLI kiểm tra kết nối, không tạo clip:

```powershell
.\.venv\Scripts\python.exe -m pipeline.ai_video models
```

CLI tạo **một clip có phí** (`--yes` là xác nhận gửi POST). Bỏ `--yes` thì chỉ hiển thị chi phí tham khảo:

```powershell
.\.venv\Scripts\python.exe -m pipeline.ai_video create --project output/trong-dung-video-cho-nguoi-moi-7ace8eb1 --model veo-3.1 --seconds 4 --format tiktok --prompt "Cận cảnh bàn tay thao tác trên bàn phím tại góc dựng video, máy quay tiến nhẹ, ánh sáng tự nhiên, không chữ và không logo." --yes
```

Tiếp tục job có sẵn:

```powershell
.\.venv\Scripts\python.exe -m pipeline.ai_video resume output/<project>/ai_video/<hash>.json
```

Nếu job chưa có ID do mất phản hồi, thêm `--remote-id <ID_lấy_từ_dashboard>` vào lệnh resume. Không dùng create để thử lại khi chưa đối chiếu lần gửi trước. Tài liệu/tham số/giá tham khảo: https://api.buihuuthang.com/docs/video (đối chiếu ngày 20/10/2026).

`pytest.ini` chỉ thu thập suite trong `tests/`. Script Gemini chạy tay ở thư mục gốc có `main()` guard, không gọi `load_dotenv()` hoặc API khi pytest/import nạp module. Trước mỗi test, fixture autouse xóa biến cấu hình ứng dụng/SDK liên quan, chuyển file mặc định sang file tạm rỗng cho cả Settings và Diagnostics, và chặn đọc `.env` thật. Test cần env sẽ tự tạo file/biến giả, được hoàn tác sau test. Test CLI ở process con dùng cùng cơ chế file tạm qua bootstrap.

Precedence production không đổi: biến môi trường > file được chỉ định (hoặc `.env` mặc định) > giá trị mặc định. `get_settings(path)` không tự nạp thêm file khác và không ghi `os.environ`. Lỗi timeout 15 thành 30 có thể xảy ra nếu script import-side-effect đã đưa timeout thật vào môi trường trước test; không phải đọc nhầm file truyền vào.

Tool Python chạy local trên Windows để nghiên cứu → lập kế hoạch JSON → dựng video bằng code.

**Trạng thái: hoàn thành Giai đoạn 5.** Researcher → brief.json, Director → edit_plan.json, Assets → audio/b-roll/manifest/resolved plan, Editor → MP4; UI có Research, Edit Plan, Assets và Render.

Đã bổ sung trang **Tạo video** ở đầu sidebar: chạy toàn bộ pipeline bằng một nút, có checkpoint/resume và chế độ duyệt kịch bản. Các module giai đoạn vẫn được gọi trực tiếp, không parse terminal hoặc chạy lại bằng subprocess.

## Chạy thử Giai đoạn 4 — Assets

Chạy từng lệnh trong PowerShell:

```powershell
Set-Location 'C:\Users\admin\Desktop\app create video\video_ai_tool'
```

```powershell
.\.venv\Scripts\python.exe -m pipeline.assets "output/trong-dung-video-cho-nguoi-moi-7ace8eb1/edit_plan.json"
```

Thay đường dẫn bằng Edit Plan của project cần dùng. Thêm `--debug` để in traceback đã che key. Bước này không gọi Gemini hoặc chạy lại Researcher/Director. Edge TTS cần mạng nhưng không cần API key.

Muốn có stock thật, điền `PIXABAY_API_KEY` bằng editor. Pixabay là nguồn chính. `PEXELS_API_KEY` tùy chọn: để trống thì bỏ qua êm, không gọi API hay báo lỗi thiếu key Pexels. Không hiển thị/ghi key vào UI, credits, cache hoặc log.

Kết quả trong thư mục project:

| Artifact | Nội dung |
| --- | --- |
| `audio/scene_<id>.mp3` | Giọng theo trường voice và narration, đo thời lượng thật bằng FFmpeg |
| `clips/` | Video/ảnh stock đã tải hoặc PNG nền màu/chữ fallback |
| `edit_plan.resolved.json` | Shot đã căn theo audio, metadata hash và cảnh báo |
| `assets.json` | Audio, clip, nguồn/tác giả, fallback và trạng thái từng cảnh/shot |
| `credits.txt` | Nguồn, tác giả, URL từng tài nguyên đang dùng; nền tự tạo được ghi riêng |

**Không ghi đè `edit_plan.json`.** MP3 được decode bằng FFmpeg đi kèm và đếm sample để đo thời lượng, không ước lượng từ số chữ/bitrate. Shot được chia/căn lại trong khoảng 1.5–4.0s và tổng mỗi cảnh khớp audio thật. Cảnh dài thêm shot, cảnh ngắn có thể giảm/gộp shot. Audio ngắn dưới 1.5s được thêm khoảng lặng; không cắt narration.

Hook có audio >3s hoặc tổng audio lệch mục tiêu >10% sẽ có cảnh báo, không tự đổi tốc độ giọng để ép số giây. `ResolvedEditPlan` cho phép thời lượng hook thực tế này; validator của Edit Plan gốc vẫn giữ hook ≤3s. Nếu muốn bám mục tiêu cũ, sửa lời đọc ở Edit Plan rồi tạo lại Assets. Không nhập resolved plan làm đầu vào CLI Assets; luôn dùng file gốc.

### Cache, stock và lỗi

- TTS cache theo hash narration + voice + rate trong `.cache/tts/`. Đổi lời đọc/giọng sẽ tạo cache mới, không dùng nhầm audio cũ.
- Stock search cache theo provider + query + format + loại video/ảnh, tối thiểu 24 giờ. File tải cache theo provider/asset/URL trong `.cache/stock_files/`, rồi copy vào project để dùng local.
- Video được ưu tiên trước ảnh; trong từng provider ưu tiên đúng orientation và dài đủ shot. Pixabay video không có bộ lọc orientation API, nên code lọc theo kích thước metadata rồi kiểm tra kích thước file thật. Pexels gửi orientation trong request.
- Video sai orientation bị bỏ qua; ảnh khác tỷ lệ được đánh dấu cần crop. Clip quá ngắn có `requires_loop=true`, ghi rõ fallback; bước render sau mới thực thi crop/loop.
- Không có stock phù hợp hoặc API/download lỗi thì thử nguồn/ảnh khác, cuối cùng tạo nền màu dùng text_overlay hoặc lời đọc. Shot có fallback/fallback_reason rõ ràng trong manifest và UI.
- Chỉ cho tải HTTPS từ các host Pixabay/Pexels/CDN đã cho phép; kiểm tra lại từng redirect và file tải. Không tải YouTube/TikTok/Facebook/Instagram hay CDN ngoài danh sách.
- Local rate limiter Pixabay dùng sliding window 90 request/60 giây, khóa file liên tiến trình, đếm cả retry và tôn trọng header cooldown/reset khi hết lượt. Đây là trần bảo thủ dưới mức mặc định 100/60 của dịch vụ; không biết các ứng dụng khác cùng key. Tham khảo [Pixabay API](https://pixabay.com/api/docs/).
- Timeout, retry lỗi mạng/429/5xx và lỗi gốc nằm trong `logs/assets_errors.log`; traceback và response lỗi được che credentials. Có thể bật debug trong CLI/UI.

TTS lỗi một cảnh không làm mất các cảnh đã thành công: manifest có `status=partial`, scene đó không có audio và ghi lỗi; giữ thời gian dự kiến cho riêng cảnh lỗi. Chạy lại để dùng cache và thử lại cảnh thiếu. CLI trả exit code 2 khi partial, 0 khi complete (có thể vẫn có stock fallback), 1 khi không tạo được manifest. Không thay bằng giọng khác hoặc tạo file im lặng để giả vờ TTS thành công.

### UI Assets

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

Mở `http://127.0.0.1:8501`, chọn project rồi trang **Assets**:

1. Nhấn **Tạo Assets**, xem thanh tiến trình theo cảnh.
2. Xem số audio đã tạo, tổng thời lượng resolved, số shot fallback và cảnh báo.
3. Chọn cảnh để nghe audio, xem video/ảnh của từng shot cùng nguồn/tác giả.
4. Sửa query ngay ở shot rồi nhấn **Tìm lại clip cho shot này**. Chỉ shot đó được tìm/cập nhật; audio và các shot khác không đổi. Nếu query giữ nguyên, ưu tiên chọn tài nguyên khác khi có.
5. Query chỉnh riêng shot được giữ khi chạy lại cùng Edit Plan. Khi file gốc đổi, UI yêu cầu tạo lại Assets; không dùng nhầm cache/manifest của kế hoạch cũ.

Các file clip cũ có thể vẫn nằm trong thư mục, nhưng UI/credits chỉ dùng danh sách hiện tại trong manifest. Không có nút render ở giai đoạn này.

### Checklist và kết quả xác minh

- [ ] Có audio từng cảnh đúng tên; nghe được trên UI.
- [ ] File gốc giữ nguyên, có `edit_plan.resolved.json`, `assets.json` và `credits.txt` riêng.
- [ ] Tổng shot trong mỗi cảnh có audio khớp audio thật, mọi shot nằm trong 1.5–4.0s.
- [ ] Nếu có key Pixabay hợp lệ, tìm được stock phù hợp hoặc thấy fallback rõ ràng khi không có kết quả.
- [ ] Pexels để trống không gây lỗi; nguồn và tác giả stock có trong credits.
- [ ] Đổi query một shot không tạo lại audio hoặc thay các shot khác.
- [ ] Chạy lại tái sử dụng cache; cảnh TTS lỗi không báo audio thành công giả.
- [ ] Không có MP4 tổng hợp/render mới.

Đã chạy thật với project mẫu: đủ 6/6 MP3; thời lượng decode khoảng 24.82 giây (khác mục tiêu 45 giây nên có cảnh báo). Cả hai key stock đang trống trong lần kiểm tra, nên 11 shot dùng nền màu fallback, không giả ghi credit stock. Lần đầu Edge TTS có `NoAudioReceived` ở một cảnh; chạy lại hoàn tất nhờ cache các cảnh còn lại. Các adapter stock được kiểm tra bằng HTTP giả lập; chưa xác minh stock thật khi chưa có key.

Đã chạy đạt 118 test offline và `pip check` không có xung đột. Kiểm thử bao gồm MP3/FFmpeg thật local, padding, chia shot, cache, optional provider, HTTP 429/cooldown, chặn redirect sang mạng xã hội, giữ file gốc, cập nhật riêng shot và Streamlit preview. Import media không tự nạp `.env` vào biến môi trường tiến trình.

## Chạy thử Giai đoạn 3 — Director

Đã thêm `GEMINI_DIRECTOR_MODEL=` vào `.env` và `.env.example`, giữ nguyên các giá trị cũ. Để trống sẽ dùng `GEMINI_MODEL`. Muốn chọn model khác, sửa riêng dòng này bằng editor; không đưa key vào terminal/chat. Sidebar hiển thị model Researcher và model Director hiệu lực.

Chạy từng lệnh PowerShell:

```powershell
Set-Location 'C:\Users\admin\Desktop\app create video\video_ai_tool'
```

```powershell
.\.venv\Scripts\python.exe -m agents.director "output/trong-dung-video-cho-nguoi-moi-7ace8eb1/brief.json" --type review --format tiktok --duration 45
```

Thay đường dẫn bằng `brief.json` của project cần dùng. Loại video hỗ trợ `news`, `review`, `story`; khổ `tiktok`, `youtube`; thời lượng MVP 6–600 giây. Thêm `--debug` để xem traceback đã che credentials. CLI không chạy lại Researcher và không tìm web.

Kết quả: `edit_plan.json` cạnh `brief.json`. Đã chạy API thật thành công trên project mẫu: tổng thời lượng 45.0 giây, đúng yêu cầu 45 giây, qua kiểm tra schema và lượt rà soát căn cứ. Các lỗi API/schema/duration/grounding và traceback nằm trong `logs/director_errors.log`; key được che như Giai đoạn 2. Lỗi không ghi đè kế hoạch thành công trước đó.

Kiểm tra cuối Giai đoạn 3: 91 test offline đạt; `pip check` không phát hiện xung đột. AppTest kiểm tra tạo kế hoạch, sửa lời đọc và query trong bảng, lưu qua cùng hàm backend. Kế hoạch chạy API thật có 6 cảnh, tổng 45.0 giây; log Director không chứa credentials đã nạp.

Backend dùng chung:

- `agents.director.run_director(...)`: CLI và UI cùng gọi để tạo kế hoạch.
- `agents.director.save_edit_plan(...)`: lưu chỉnh sửa sau kiểm tra schema, thời lượng, brief hash và căn cứ.
- `create_edit_plan(...)`: tách provider để kiểm thử bằng LLM giả lập; cache theo brief, tham số, model, schema và prompt.

Code tính bảng gợi ý phân bổ scene/shot đủ thời lượng trước khi gọi model; output vẫn phải validate độc lập trong ±10%, shot 1.5–4 giây, hook tối đa 3 giây, CTA cuối, ID duy nhất. Mỗi cảnh có `fact_ids` (index 1-based trong brief), cùng `pattern_interrupt`; không để khoảng kế hoạch vượt 10 giây thiếu interrupt có SFX/overlay/effect. Cảnh không phải CTA cần fact tham chiếu.

Chỉ truyền claim có trong brief vào Director, không dùng hooks/tín hiệu xã hội làm căn cứ mới. Code chặn số viết bằng chữ số không có trong fact tham chiếu; sau đó gọi model rà soát cả khẳng định bằng chữ, tiêu đề, lời đọc và overlay. Cấm các cụm “chưa xác minh”, “chưa kiểm chứng”, “cần xác minh” trong narration và chữ trên hình; gặp thì sinh lại. Fact một nguồn dùng “Theo <tên miền>, …”, fact có ít nhất hai nguồn thì viết thẳng bằng lời mới. Ghi chú kiểm chứng nằm riêng trong `scene.review_notes`: fact_ids, source_count, confidence và các nguồn/URL theo từng fact. Metadata được code tính từ brief khi tạo/lưu, không tin số nguồn do model điền. Chỉ gộp các claim giống nhau sau chuẩn hóa; nhiều URL cùng tên miền không làm tăng số nguồn, nguồn của các claim khác nhau không chứng minh một claim có nhiều nguồn. Lượt rà soát dùng cùng model Director, có cache; đây là kiểm tra bằng AI, vẫn cần người dùng duyệt nội dung trước sản xuất.

Metadata bổ sung trong JSON: `video_type`, `target_duration_sec`, `brief_hash`; cảnh có `fact_ids`, `pattern_interrupt`. Khi brief thay đổi, không lưu kế hoạch cũ dựa trên brief hash khác; cần tạo lại. Thời lượng hiện tại tính theo shot, chưa đo giọng thật; Giai đoạn 4 mới căn lại audio.

### UI Edit Plan

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

1. Mở `http://127.0.0.1:8501`, chọn project có brief, chọn trang **Edit Plan**.
2. Chọn loại video, khổ và thời lượng, nhấn **Tạo Edit Plan**. UI gọi cùng hàm với CLI.
3. Xem tổng thời lượng và từng cảnh: vai trò, lời đọc, fact_ids, bảng shot, chuyển cảnh/SFX và interrupt.
4. Sửa lời đọc ở ô văn bản; sửa cột **Từ khóa b-roll** trực tiếp trong bảng. Từ khóa cần 2–4 từ tiếng Anh.
5. Nhấn **Lưu chỉnh sửa** để validate và rà soát căn cứ rồi ghi atomic vào `edit_plan.json`. Tác vụ này có thể dùng quota Gemini; code bổ sung dẫn nguồn báo chí khi cần. Cụm cảnh báo kiểm chứng hoặc claim thiếu nguồn bị từ chối; ghi chú kiểm chứng được lưu riêng trong review_notes.
6. JSON đã lưu có thể xem/tải. Không có nút tạo audio hoặc render ở giai đoạn này.

Checklist Giai đoạn 3:

- [ ] CLI báo `Hoàn tất` và có `edit_plan.json` cạnh brief.
- [ ] Model Director lấy cấu hình riêng hoặc fallback đúng model Researcher.
- [ ] Tổng thời lượng trong ±10% yêu cầu; mọi shot 1.5–4 giây, hook ≤3 giây, CTA cuối.
- [ ] Cảnh dẫn fact_ids hợp lệ; claim ngoài brief bị từ chối; kiểm chứng và badge “1 nguồn” xuất hiện dưới cảnh trên UI, lời đọc/chữ trên hình không có câu cảnh báo kiểm chứng.
- [ ] UI có trang Edit Plan; sửa lời đọc và query rồi lưu, đổi project/quay lại vẫn thấy nội dung đã lưu.
- [ ] Kế hoạch cũ được giữ khi tạo/lưu mới thất bại; debug xem được lỗi gốc đã che credentials.
- [ ] Chưa có audio/video render mới.

Lỗi thường gặp: brief không có fact thì nghiên cứu lại; cảnh gồm nhiều fact một nguồn khác nhau phải ghi “Theo <nguồn>” ở đúng mệnh đề; query ngoài 2–4 từ Latin thì sửa lại; API 429 thì đợi quota; kế hoạch thiếu metadata/brief đã đổi thì tạo lại. `on_screen_text` được chấp nhận khi đọc shot JSON, lưu tên chuẩn `text_overlay` để Assets/Render tiếp tục dùng được; overlay tối đa 12 từ. Muốn áp dụng chính sách mới cho project cũ, tạo lại Edit Plan rồi tạo lại Assets (audio/resolved plan) trước khi Render. Nếu model không tuân thủ sau retry, xem `director_errors.log` và chọn model Director khác có structured output tốt hơn.

## UI web local (Research)

Chạy từng lệnh trong PowerShell, không cần activate venv:

```powershell
Set-Location 'C:\Users\admin\Desktop\app create video\video_ai_tool'
```

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

Mở `http://127.0.0.1:8501`. Dừng server bằng `Ctrl+C`. Nếu đang activate venv, có thể dùng đúng lệnh ngắn:

```powershell
streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

`.streamlit/config.toml` cũng ghim địa chỉ `127.0.0.1`, chạy headless và tắt usage statistics. Không đổi địa chỉ thành `0.0.0.0`. Nếu cổng 8501 đang dùng, thêm `--server.port 8502` và mở đúng cổng mới.

UI chỉ lấy cấu hình qua `get_settings()`. Sidebar hiển thị “Đã có/Chưa có” cho bốn API key cùng tên model; không có trường nhập key, trình đọc `.env`, hoặc hiển thị Settings/raw cấu hình. Trạng thái “Đã có” không xác minh key còn hạn hoặc có quyền gọi API. Các lỗi và artifact hiển thị/tải đều đi qua bộ lọc credentials. Debug chỉ mở traceback đã che key trong expander; UI không parse terminal và không gọi subprocess.

### Cách dùng và checklist

1. Chọn project đã có trong sidebar để xem dữ liệu do CLI hoặc UI tạo. Project được phát hiện trực tiếp từ các thư mục con của `output/`; bỏ qua thư mục ẩn, symlink và `source_debug`.
2. Nhấn **Project mới**, nhập chủ đề, giới hạn nguồn web. Bật **YouTube trends** nếu cần gợi ý hook/góc khai thác, chọn số ngày (mặc định 14), ưu tiên tiếng Việt rồi nhấn **Chạy Researcher**. Nút chạy bị khóa nếu thiếu key/model Gemini.
3. Trong lúc chạy có spinner và thông báo tiến độ. UI gọi trực tiếp `agents.researcher.run_research()`, dùng cùng cache/quota/validation với CLI, không chạy nghiên cứu lại khi chỉ xem trang hoặc tải file.
4. Chạy thành công sẽ tự chọn project vừa tạo. Mỗi project UI mới có thư mục riêng, kể cả trùng chủ đề; chạy lại project đang chọn cập nhật artifact trong project đó.
5. Tab **Research Brief** có facts với link nguồn, góc tiếp cận, hooks, câu hỏi, từ khóa và rủi ro. Tab **Nguồn đối chiếu** xem `sources.json`. Tab **JSON thô** xem và tải `brief.json`.
6. Nếu lỗi, UI hiển thị nguyên nhân gốc với hướng dẫn tiếng Việt; bật **Chế độ debug** để xem traceback đã che key. Project tạo trước khi lỗi được giữ lại và tự chọn để chạy tiếp. Nếu project từng thành công, brief cũ vẫn hiển thị khi lượt mới lỗi; đó là kết quả cũ.

UI không gọi API khi chỉ mở project. Nhấn chạy Researcher có thể sử dụng quota/chi phí của tài khoản. UI bản mỏng chạy đồng bộ một lượt trong session; chưa có hàng đợi, tiến trình nền, hủy job hoặc chỉnh sửa Edit Plan.

Đã kiểm tra 61 test offline, gồm Streamlit AppTest cho tạo/chọn project, đọc artifact, submit form qua hàm dùng chung và bảo vệ key khi có lỗi. Server đã khởi động thành công ở địa chỉ loopback. Không gọi thêm Gemini thật trong quá trình kiểm thử UI.

### Thêm trang cho giai đoạn sau

- Giữ logic độc lập Streamlit trong `agents/`, `pipeline/`, `providers/` và `editor/`; CLI và UI cùng gọi một hàm xử lý.
- Tạo file view trong `app/views/`, ví dụ `director.py`, `assets.py`, `render.py`, với hàm `render(settings, project, topic, debug, diagnostics)` như trang Research. Dùng `project` đang chọn làm thư mục đọc/ghi artifact.
- Import renderer và thêm vào dict `PAGES` trong `app/streamlit_app.py`. Sidebar tự hiện tên trang mới; không cần sửa bộ quản lý project.
- **Director / Edit Plan:** đọc `brief.json`, gọi Director dùng chung, validate và lưu `edit_plan.json`; view có thể thêm editor JSON/kịch bản.
- **Assets:** đọc Edit Plan, gọi bước TTS/stock dùng chung, hiển thị audio, danh sách clip, cảnh thiếu tài nguyên và credits.
- **Render:** đọc plan/assets, gọi editor dùng chung, hiển thị preview/video và nút tải MP4.

Các trang Research, Edit Plan và Assets đã được thêm. Render sẽ được thêm ở Giai đoạn 5. `pipeline/projects.py` quản lý thư mục/artifact; `app/ui_errors.py` định dạng lỗi an toàn; mỗi view chỉ phụ trách widget và trình bày.

## Chạy thử Giai đoạn 2

Điền `GEMINI_API_KEY` và `GEMINI_MODEL` hợp lệ trong `.env` bằng trình soạn thảo. Thêm `YOUTUBE_API_KEY` nếu muốn dùng YouTube Data API v3; cần bật API trong Google Cloud. Không dùng lệnh in `.env`, không đưa key vào dòng lệnh, log hoặc Git. CLI không in output AI thô, HTTP exception hoặc dữ liệu cấu hình.

Lỗi Gemini/JSON có loại exception, thông điệp gốc và traceback trong `logs/researcher_errors.log`, sau khi che credentials. Thêm `--debug` để in cùng traceback đã che credentials ra stderr. Không ghi locals, cấu hình hoặc nội dung `.env`. `logs/` vẫn nằm trong `.gitignore`.

```powershell
.\.venv\Scripts\python.exe -m agents.researcher "trong dựng video cho người mới" --no-youtube --web-limit 3 --debug
```

Đã tái hiện và sửa lỗi HTTP 400 `Unknown name "additional_properties"`: JSON Schema của Pydantic có `additionalProperties: false` do `extra="forbid"`. Khi truyền class qua `response_schema`, SDK gửi keyword dưới dạng không phù hợp với trường Schema của endpoint. Provider hiện dùng `response_json_schema=model.model_json_schema()`, giữ nguyên validate nghiêm ngặt phía Python. Đã xác minh bằng API thật: lệnh trên xuất brief có 3 fact cùng sources đối chiếu.

Provider còn phân biệt output rỗng, prompt/output bị chặn an toàn và `MAX_TOKENS`. Ngân sách output ban đầu 8192 token; nếu bị cắt, lần retry nội dung tăng ngân sách, tối đa 32768. Không dùng JSON bị cắt như brief hợp lệ. Lỗi parse/grounding được ghi vào log và retry theo giới hạn; safety block dừng với nguyên nhân cụ thể. Bộ kiểm thử hiện đạt 56 test offline.

```powershell
Set-Location 'C:\Users\admin\Desktop\app create video\video_ai_tool'
.\.venv\Scripts\python.exe -m agents.researcher "Ứng dụng AI trong dựng video cho người mới" --youtube-days 14 --youtube-limit 5
```

Thử nhanh chỉ với web (không cần key YouTube):

```powershell
.\.venv\Scripts\python.exe -m agents.researcher "Ứng dụng AI trong dựng video cho người mới" --no-youtube --web-limit 3
```

Researcher luôn không tải video/transcript. `--no-transcripts` chỉ còn để tương thích lệnh cũ và không bật/tắt việc tải transcript. CLI bật trends mặc định, `--no-youtube` tắt hoàn toàn; `--youtube-language vi` dùng regionCode=VN, relevanceLanguage=vi, `all` bỏ bộ lọc này. Hai lệnh trên gọi Gemini thật và có thể dùng quota/chi phí tài khoản.

Kết quả thành công nằm trong `output/<slug-chủ-đề>-<hash8>/`:

- `brief.json`: ResearchBrief tiếng Việt, có nguồn URL, confidence và trích đoạn dẫn chứng của từng fact.
- `sources.json`: văn bản nguồn web, thời điểm thu thập, trend_signals YouTube riêng, thống kê lọc fact và cảnh báo fallback; không có transcript.

Các file chỉ được xuất khi Research Brief hợp lệ. Nếu lượt chạy thất bại, artifact của lượt thành công trước được giữ lại. Không coi file cũ là kết quả của lượt thất bại mới. Cache nguồn vẫn được giữ để chạy lại.

Checklist:

- [ ] Lệnh báo `Hoàn tất` và đường dẫn tới `brief.json`.
- [ ] Mỗi fact có URL web trong `sources.json` và `evidence_quote` xuất hiện trong văn bản nguồn.
- [ ] Quote ngắn tối đa 25 từ; claim được diễn đạt lại, không phải transcript chép nguyên văn.
- [ ] Nguồn snippet chỉ có confidence thấp. Nguồn bài viết đơn lẻ tối đa medium.
- [ ] YouTube chỉ đóng góp tín hiệu, không được dùng làm nguồn fact hoặc tải ảnh/video.
- [ ] Nguồn thiếu/lỗi xuất hiện trong `risks`; không có nguồn nào thì lệnh dừng, không bịa brief.
- [ ] Chạy lại cùng nguồn/model/prompt dùng cache; cache brief vẫn được validate lại.

Không cần key hoặc mạng để chạy kiểm thử:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

Đã xác minh 56 kiểm thử offline, trong đó có pipeline bằng provider giả lập, adapter Gemini qua HTTP mock, bảo vệ thông báo lỗi/traceback, safety/empty/token-limit, dẫn chứng, quota và fallback. Đã chạy API thật thành công với chủ đề “trong dựng video cho người mới”, chế độ chỉ web và 3 nguồn. Chất lượng/nội dung nguồn vẫn cần người dùng rà soát. Có một DeprecationWarning từ `google-genai` trên Python 3.14; không làm test thất bại.

Debug từng nguồn:

```powershell
.\.venv\Scripts\python.exe -m sources.web_search "dựng video AI" --limit 3
```

Kết quả debug web được lưu vào `output/source_debug/`; không in payload ra terminal. `--output-dir` của Researcher cho phép đổi thư mục kết quả. `--help` liệt kê toàn bộ tham số. Kiểm tra YouTube trends qua Researcher, không dùng adapter transcript cũ.

### Cache, quota và giới hạn căn cứ

Cache DDGS, nội dung bài viết, metadata/bình luận YouTube, Gemini trend_insights và Research Brief nằm trong `.cache/`, TTL theo `CACHE_TTL_SEC`. Cache không chứa key hay nội dung `.env`. Thay model/prompt/nội dung nguồn sẽ đổi khóa cache brief. Không cache output LLM chưa hợp lệ.

`youtube_quota.json` lưu quota ước tính và số lần search, được khóa giữa các tiến trình, ghi atomic, reset theo ngày Pacific. Bộ đếm đặt trước cho từng request và cả retry; cache hit không tốn quota. Áp dụng trần search mỗi lượt, tối đa 100 search/ngày local và ngân sách `YOUTUBE_DAILY_QUOTA`. File quota hỏng sẽ chặn gọi API thay vì tự reset.

Luồng YouTube trends mới đặt trước 1 đơn vị mỗi search/videos/commentThreads request, kể cả retry; search còn bị giới hạn riêng 100 lần/ngày và YOUTUBE_MAX_SEARCHES_PER_RUN. Cùng chủ đề/ngày/cửa sổ/language/limit dùng lại cache search; metadata và bình luận có cache riêng. Top 3 video theo views lấy tối đa 10 bình luận/video (order=relevance, plainText). Logs/researcher_errors.log ghi số request/quota local theo lượt và tổng ngày, không ghi key. Adapter YouTube cũ còn giữ budget bảo thủ 100/search và dùng chung ledger; bộ đếm là ước tính local, không biết ứng dụng khác cùng project. Hạn mức thực xem Google Cloud Console. Xem [Search API](https://developers.google.com/youtube/v3/docs/search/list), [Videos API](https://developers.google.com/youtube/v3/docs/videos/list), [CommentThreads API](https://developers.google.com/youtube/v3/docs/commentThreads/list).

YouTube trends hoàn toàn tách khỏi facts: `trend_signals` chứa platform/title/channel/url/views/likes/comments/published_at/hashtags/top_comments. Gemini gọi bước riêng với schema `TrendInsights`; mỗi danh mục hook_patterns/keywords/common_questions/angles gồm các phần tử `{text, reason, evidence_urls}`. URL phải thuộc tín hiệu đã thu thập; câu hỏi cần video có bình luận. Không có bằng chứng thì để danh mục rỗng. Gemini hoặc YouTube lỗi/hết quota chỉ thêm cảnh báo, giữ facts web đã hợp lệ; metadata vẫn được giữ khi lỗi tóm tắt. Director dùng insights làm gợi ý cách dẫn/góc khai thác, audit vẫn chỉ chấp nhận claim trong fact_ids. UI hiển thị bảng video nhiều view, gợi ý và lý do; số view là ảnh chụp thống kê, không chứng minh video đang viral hay nội dung là thật.

Fact được đối chiếu URL và quote nguyên văn trong nguồn; cách kiểm tra này không chứng minh claim là đúng hoặc quote hỗ trợ đầy đủ ý nghĩa claim. Cần rà soát `brief.json`/`sources.json` trước giai đoạn kịch bản. Thống kê YouTube trong cache là số liệu quan sát tại thời điểm lấy, không phải số liệu realtime hay bằng chứng tăng trưởng.

Lỗi thường gặp:

| Thông báo/tình huống | Cách xử lý |
| --- | --- |
| Thiếu/sai cấu hình Gemini | Điền key và model được tài khoản hỗ trợ bằng editor; không gửi key vào chat |
| Gemini 429/quota | Đợi giới hạn phục hồi hoặc kiểm tra quota/billing của model |
| Không có nguồn | Đổi từ khóa cụ thể hơn, kiểm tra proxy/mạng; DDGS có thể bị rate limit |
| YouTube thiếu key/lỗi/quota | Researcher tiếp tục với web; kiểm tra API được bật và quyền của key |
| Không có transcript | Dùng metadata hoặc chạy với `--no-transcripts` |
| JSON/dẫn chứng sai sau retry | Giảm phạm vi chủ đề, chọn model khác có structured output; không có brief mới được ghi |
| File quota local hỏng | Kiểm tra bản sao lưu quota; không xóa bộ đếm chỉ để vượt giới hạn trong ngày |
| Muốn lấy lại dữ liệu mới | Đợi TTL hết hoặc giảm `CACHE_TTL_SEC`; không cần xóa file quota |

## Cài đặt trên Windows PowerShell

Python 3.11+; ưu tiên 3.11–3.13 cho hệ sinh thái media. Bộ dependencies đã cài thành công trên Python 3.14.4 của máy hiện tại; khung Giai đoạn 1 đạt 27 kiểm thử offline. Chức năng render sẽ được kiểm tra ở Giai đoạn 5. Không cài thư viện vào Python hệ thống.

```powershell
Set-Location 'C:\Users\admin\Desktop\app create video\video_ai_tool'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe main.py --check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

Không cần activate venv; cách trên tránh lỗi ExecutionPolicy. Nếu đã có Python 3.13 qua Python Launcher, có thể tạo môi trường mới bằng `py -3.13 -m venv .venv` trước bước cài đặt. Không ghi đè môi trường đang dùng bằng phiên bản Python khác.

Kiểm tra riêng cấu hình:

```powershell
.\.venv\Scripts\python.exe -m config.settings
```

## Checklist Giai đoạn 1

- [ ] Cài dependencies không báo lỗi.
- [ ] `main.py --check` in `OK`, tạo `.cache/`, `output/`, `logs/` và không gọi API.
- [ ] Pytest chạy thành công; không yêu cầu API key hoặc kết nối mạng.
- [ ] `pip check` báo không có xung đột dependencies.
- [ ] Không có API key thật trong file source; `.env` được gitignore.

## Cấu hình

Sao chép `.env.example` thành `.env` và nhập key khi bắt đầu giai đoạn cần provider đó. Biến môi trường có ưu tiên cao hơn `.env`. Dự án đọc `.env` theo vị trí `config/settings.py`, không phụ thuộc working directory.

| Biến | Mục đích |
| --- | --- |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | SDK `google-genai`; chọn model tài khoản được phép dùng |
| `YOUTUBE_API_KEY` | Data API v3, chỉ metadata/tín hiệu |
| `PEXELS_API_KEY`, `PIXABAY_API_KEY` | Stock media |
| `DEFAULT_VOICE` | HoaiMy hoặc NamMinh tiếng Việt |
| `REQUEST_TIMEOUT_SEC`, `RETRY_ATTEMPTS` | Timeout và số lần thử mạng |
| `CACHE_TTL_SEC` | TTL cache JSON |
| `YOUTUBE_DAILY_QUOTA` | Trần quota do người dùng cấu hình, không vượt 10.000 |
| `YOUTUBE_MAX_SEARCHES_PER_RUN` | Trần search mỗi lượt; bộ đếm thực hiện ở Giai đoạn 2 |

Key được bọc `SecretStr`. Kiểm tra offline không yêu cầu key; `require_key()` báo thiếu key bằng tiếng Việt khi provider thực sự cần dùng.

## Cấu trúc

```text
video_ai_tool/
├── .env.example, .gitignore, requirements.txt, README.md, main.py
├── app/streamlit_app.py
├── config/{settings,presets}.py
├── prompts/{researcher,director_news,director_review,director_story}.txt
├── schemas/{base,research_brief,edit_plan}.py
├── agents/{researcher,director}.py
├── sources/{web_search,youtube,transcripts,social_signals}.py
├── providers/{llm_base,llm_gemini,tts_edge,stock_pexels,stock_pixabay}.py
├── pipeline/{run,assets}.py
├── editor/{timeline,effects,captions,audio_mix,render}.py
├── utils/{cache,retry,text,logger}.py
├── assets/{fonts,music,sfx}/
├── output/
├── logs/
└── tests/{test_schemas,test_timeline,test_utils}.py
```

`test_timeline.py` kiểm tra Editor bằng media sinh offline và FFmpeg đi kèm. Chỉ bổ sung font, nhạc hoặc SFX có quyền sử dụng và giữ file license/nguồn đi kèm.

## Hợp đồng dữ liệu

`ResearchBrief` giữ đúng field yêu cầu, bắt buộc source URL HTTP(S) cho fact và evidence URL cho trend. `EditPlan` giữ đúng field yêu cầu, chặn field ngoài schema, giá trị không hữu hạn, shot ngoài 1,5–4 giây, query không có dạng 2–4 từ Latin, ID trùng, thiếu hook/CTA và hook dài hơn 3 giây. Query cần kiểm tra ngữ nghĩa tiếng Anh ở Director; schema không thể tự chứng minh ngôn ngữ hoặc tính đúng của nguồn.

`plan.validate_target_duration(seconds)` kiểm tra tổng thời lượng ±10%. Tính đúng của fact, sự phù hợp hook, khoảng cách pattern interrupt và việc kịch bản chỉ dùng fact đã có trong brief sẽ cần kiểm tra tại Director/editor ở các giai đoạn tương ứng; schema không được coi là kiểm chứng nội dung.

Cache dùng SHA-256 cho input JSON chuẩn hóa, có namespace, TTL, atomic replace và bỏ qua file hỏng. Không đưa API key vào input cache. Wrapper HTTP thử lại timeout, mất kết nối, HTTP 408/429/5xx với exponential jitter; không thử lại 401/403/404. Provider SDK khác sẽ có bộ phân loại lỗi tương ứng khi được triển khai. Logger có che một số dạng key phổ biến; không log payload hoặc exception thô chứa bí mật.

## Nguyên tắc media và nguồn

- AI chỉ sinh JSON; code validate rồi mới thực thi kế hoạch.
- YouTube chỉ lấy tín hiệu/metadata/transcript, không tải media làm b-roll.
- Chưa scrape TikTok/Facebook/Instagram; `social_signals.py` dành cho adapter API tương lai.
- B-roll từ Pexels/Pixabay hoặc nội dung AI được phép sử dụng; kiểm tra license của từng asset khi tải và ghi tác giả, URL, nguồn vào `credits.txt`.
- Không tự tạo bằng chứng hoặc số liệu. Fact chưa kiểm chứng phải có confidence thấp; không trình bày như sự thật chắc chắn.

## Lỗi thường gặp

| Lỗi | Cách xử lý |
| --- | --- |
| `No module named pydantic` | Dùng đúng `.venv\Scripts\python.exe` và cài requirements |
| Không tìm thấy Python | Cài Python 3.11–3.13, bật PATH và mở PowerShell mới |
| Pillow yêu cầu compiler trên Python 3.14 | Dùng venv Python 3.13; không nâng Pillow lên 12+ vì MoviePy 2.2.1 yêu cầu `<12` |
| Pip không truy cập mạng | Kiểm tra proxy, firewall hoặc quyền tải PyPI; không tắt xác minh TLS |
| Cấu hình không hợp lệ | So sánh kiểu/khoảng giá trị với `.env.example`; timeout >0, retry 1–8 |
| `Thiếu ..._API_KEY` | Điền key vào `.env` khi đến giai đoạn gọi provider; offline check không cần key |
| Gọi Researcher/UI chỉ thấy chưa triển khai | Đây là khung Giai đoạn 1; xác nhận để sang giai đoạn tương ứng |

## Các giai đoạn tiếp theo

2. Đã hoàn thành: Researcher web + YouTube → `brief.json`, cache và bộ đếm quota.
3. Director: JSON validated + retry → `edit_plan.json`.
4. TTS từng cảnh, đo audio, stock b-roll có cache và credits.
5. Timeline, captions tiếng Việt, effects, audio ducking, render/preview.
6. CLI tổng hợp và resume theo artifact hợp lệ.
7. Streamlit xem/sửa kế hoạch trước khi render, phát/tải video.
8. Tuỳ chọn social API, ảnh/video AI, provider LLM thứ hai.

Dừng sau Giai đoạn 5; chưa đăng video, chưa thêm AI video.

## Giai đoạn 5 — Editor

Chạy từ thư mục `video_ai_tool`, dùng venv đã cài requirements (MoviePy 2.2.1 và imageio-ffmpeg 0.6.0). Không cần cài FFmpeg hệ thống.

```powershell
.\.venv\Scripts\python.exe -m editor.render output/trong-dung-video-cho-nguoi-moi-7ace8eb1/edit_plan.resolved.json --mode preview
```

```powershell
.\.venv\Scripts\python.exe -m editor.render output/trong-dung-video-cho-nguoi-moi-7ace8eb1/edit_plan.resolved.json --mode final
```

`--preview` và `--final` là các cách viết tắt; `--debug` bật traceback đã che credentials. Lỗi gốc ghi vào `logs/render_errors.log`.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

Chọn project → **Render** → **Render xem nhanh** hoặc **Render bản cuối**. Worker chạy trong thread riêng, fragment cập nhật tiến trình mỗi giây; có thể đổi trang trong lúc dựng. Mỗi project chỉ nhận một job đang chạy, các project được xếp hàng để tránh chiếm quá nhiều RAM. Không đóng tiến trình Streamlit khi render chưa xong.

- Preview: TikTok 540×960 / YouTube 960×540, 30 fps, preset ultrafast. Final: 1080×1920 / 1920×1080, 30 fps, libx264 CRF 20 + AAC 192k, yuv420p, faststart.
- Kết quả: `render/<slug>_<format>_<mode>.mp4`, `preview.json`/`final.json` (metadata/thời gian/cảnh báo), `credits.txt`. Chỉ ghi trong `render/` và `logs/`; không ghi đè resolved plan, manifest, audio, clips, credits nguồn.
- `assets.json`, nếu có, dùng để đối chiếu hash và ánh xạ chính xác media. Nếu thiếu manifest, tìm audio theo `audio/scene_<id>.mp3`, clip theo `clips/scene_<id>_shot_<n>_*`; nếu không tìm được clip thì dựng thẻ nền màu có text_overlay. Không tải media, không gọi mạng.
- Timeline đo audio thật; cắt/loop video nguồn, cover/crop giữa, hiệu ứng liên tục. Chuyển cảnh 0,22 giây nằm trong đuôi cảnh trước để giữ nguyên mốc giọng đọc. Thiếu audio dừng và chỉ rõ cảnh cần chạy lại Assets.
- Phụ đề tiếng Việt nhóm 2–4 từ, viền đen, highlight từ hiện tại, nằm trong vùng an toàn. Assets hiện chưa có word timestamps nên thời gian highlight được ước lượng theo số ký tự, không phải forced alignment. Có thể cung cấp `audio/scene_<id>.words.json` dạng `{"words":[{"text":"Xin","start":0.0,"end":0.3},{"text":"chào","start":0.3,"end":0.8}]}`; giây tính từ đầu cảnh, thứ tự từ phải khớp narration. Sidecar thiếu/hỏng tự chuyển sang ước lượng.
- Font ưu tiên `assets/fonts/*Bold*.otf/ttf`, rồi font khác trong thư mục; thiếu thì Arial Bold Windows. Nhạc lấy file đầu tiên theo tên trong `assets/music/`, lặp theo thời lượng, volume từ plan và ducking theo năng lượng giọng đọc. SFX tìm `assets/sfx/whoosh.*` hoặc `pop.*`; thiếu nhạc/SFX bỏ qua. Mix chuẩn hóa peak giọng và giới hạn peak tổng 0,98.
- `editor/timeline.py`, `effects.py`, `captions.py`, `audio_mix.py`, `render.py` dùng chung cho CLI/UI; `editor/jobs.py` quản lý worker, `app/views/render.py` chỉ hiển thị và gửi job.

## Tạo video bằng một nút — điều phối toàn pipeline

Mở Streamlit local, chọn trang đầu **Tạo video**. Điền chủ đề, loại video, khổ, thời lượng, giọng, chất lượng preview/final, nguồn web và YouTube trends. Nhấn **Tạo video** tạo project mới theo slug + ID ngắn, giữ nguyên project đang chọn. Worker chạy trong thread nền; có tiến trình từng bước, thời gian, nhật ký ngắn, xem/tải MP4, credits và report khi hoàn tất.

Luồng dùng lại hàm có sẵn: `run_research` → `run_director` → `run_assets` → AI tùy chọn → `run_render`. `pipeline.run_all.run_all(config, progress_cb, stop_after=None)` nhận `RunConfig` hoặc dict; callback nhận `{project, step, message, state}` là snapshot không chứa Settings/credentials. `stop_after` nhận research/director/assets/ai_video/render. Bộ điều phối không gọi API qua terminal hoặc phân tích output subprocess.

Chạy tự động từ thư mục `video_ai_tool` (mặc định AI TẮT, render preview):

```powershell
.\.venv\Scripts\python.exe -m pipeline.run_all --topic "Tin tức AI thế giới" --type news --format tiktok --duration 45
```

Thêm `--youtube-trends --youtube-days 14 --web-limit 3` để lấy tín hiệu YouTube. `--voice vi-VN-NamMinhNeural` đổi giọng; `--render-mode final` dựng bản cuối.

Chế độ duyệt:

```powershell
.\.venv\Scripts\python.exe -m pipeline.run_all --topic "Tin tức AI thế giới" --type news --format tiktok --duration 45 --review
```

Dừng sau Director. Trang Tạo video hiển thị lại trang Edit Plan hiện có; sửa và **Lưu chỉnh sửa**, rồi nhấn **Tiếp tục tạo video**. CLI tiếp tục sau duyệt:

```powershell
.\.venv\Scripts\python.exe -m pipeline.run_all --resume output/<project> --continue
```

Lỗi/hủy ở bước nào thì dừng, ghi bước lỗi và nguyên nhân; bước done chỉ được bỏ qua nếu artifact còn đủ và SHA-256 khớp. Assets partial/thiếu audio không được chuyển sang Render. Dùng `--resume output/<project>` tiếp tục sau lỗi hoặc sau khi ứng dụng bị đóng; cấu hình phải khớp lượt cũ. Kịch bản sửa ở điểm dừng duyệt được kiểm tra lại bằng luồng lưu Director trước khi dùng. Nếu artifact của bước đã xong bị thay đổi ngoài điểm duyệt, dừng rõ ràng thay vì dùng dữ liệu lệch nhau.

`--force` luôn chạy từ đầu trong project MỚI, kể cả đi cùng `--resume`; project cũ được giữ nguyên. Các module vẫn có thể dùng cache nội bộ của chúng. Nút Hủy là yêu cầu dừng ở điểm an toàn, có thể phải chờ tác vụ đang gọi API trả về; không hủy/refund job AI đã gửi. ID job được lưu để resume không tự gửi POST trùng.

Clip AI mặc định tắt. `AI_CLIP_MAX_PER_RUN=3` trong cấu hình (0 để tắt); UI/CLI đều kiểm tra trần này. Khi bật, chọn model, số clip và số giây mỗi clip. UI hiện “Sẽ tạo N clip, model X, thời lượng Y” và yêu cầu checkbox xác nhận trước khi nhấn nút chạy, cả auto và review; không hỏi lại giữa pipeline. CLI thiếu `--confirm-ai` chỉ báo thông tin xác nhận rồi thoát trước khi tạo project/gọi API:

```powershell
.\.venv\Scripts\python.exe -m pipeline.run_all --topic "Dựng video cho người mới" --type review --format tiktok --duration 45 --ai-clips 1 --ai-model veo-3.1 --ai-seconds 4 --confirm-ai
```

Số clip chọn không được vượt tổng số shot; nếu kế hoạch thiếu shot, bước AI dừng trước khi gửi API có phí. Clip AI ưu tiên thay shot fallback rồi các shot đầu, có biến thể prompt riêng cho từng vị trí. Bộ điều phối gọi lại `create_job`/`resume_job`; nguồn gốc, model và job ID được ghi vào báo cáo/credits. AI được ghép vào bộ dữ liệu dựng riêng `ai_render/` với bản sao audio/clip cần dùng; `edit_plan.json`, `edit_plan.resolved.json`, `assets.json` và credits gốc được giữ nguyên. Video cuối vẫn xuất về `render/` của project. Xác nhận được lưu theo N/model/thời lượng; resume dùng lại xác nhận cũ khi cấu hình khớp, còn `--force` có AI cần xác nhận lượt mới.

Artifact bổ sung:

- `run_state.json`: cấu hình công khai, trạng thái/timestamps/thời gian/cảnh báo/lỗi từng bước, hash artifact, nhật ký, xác nhận AI và kết quả render. Không lưu key.
- `report.md`: số fact trong brief và đã dùng, nguồn đối chiếu/nguồn fact đã dùng, tín hiệu YouTube tách riêng, cảnh báo, clip AI đã dùng, đường dẫn video và thời gian xử lý (không cộng thời gian chờ duyệt).
- `logs/run_all_errors.log`: lỗi gốc đã che credentials; lỗi chi tiết API vẫn dùng log module hiện có.

Kiểm tra toàn bộ, không gọi mạng và không đọc cấu hình thật của máy:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp -p no:cacheprovider
```

Ghi file trên Windows: JSON/credits/báo cáo dùng `utils.atomic_io`, file tạm cùng thư mục được đóng sau flush + fsync trước khi thay thế. Lỗi khóa file WinError 5/32 được thử tối đa 8 lần (50 ms đến 1 giây); nếu vẫn bị chặn đổi tên, ghi trực tiếp và cảnh báo UTF-8 trong `logs/atomic_io.log`. Thao tác thay thế audio/video cũng dùng retry và sao chép theo khối khi cần fallback. Không log nội dung artifact hay cấu hình.

UI thử đọc checkpoint lại và dùng snapshot tốt gần nhất/worker đang chạy khi file bị khóa hoặc JSON chưa hoàn chỉnh. Resume luôn yêu cầu checkpoint trên đĩa đọc được, để tránh chạy lại nhầm công việc có phí. Nếu cả ghi trực tiếp trạng thái cũng thất bại, pipeline vẫn chạy và UI cảnh báo trạng thái chỉ còn trong bộ nhớ; cần khôi phục quyền ghi trước khi đóng app/resume. Artifact nghiệp vụ và job AI vẫn phải lưu thành công trước khi dùng tiếp.

Lúc khởi động UI và bắt đầu/resume pipeline, dọn `*.tmp` cũ hơn 1 giờ trong project, bỏ qua liên kết và file đang được hàm ghi dùng chung sử dụng. Khoảng chờ này bảo vệ file tạm mới của tiến trình khác; project đang có worker giữ khóa được UI bỏ qua.

Khi gateway trả remote ID, lưu ngay vào JSON job bằng `utils.atomic_io` trước khi xử lý trạng thái/chi phí hoặc poll. Lỗi lưu ID được thử lại 3 lần ở tầng job (ngoài retry I/O), ghi ID và lỗi gốc đã che credentials vào `logs/gateway_video_errors.log`. Không gửi lại POST khi lưu thất bại; lấy ID từ thông báo/log để khôi phục.

Trang **AI Video**, và phần khôi phục khi **Tạo video** lỗi Clip AI, có ô Remote ID + nút **Tiếp tục job có sẵn** và lệnh PowerShell đầy đủ có thể copy. Nếu dashboard thực sự không có job, đánh dấu xác nhận rồi bấm **Đã kiểm tra dashboard: không có job, tạo lại**. Đây là lần gửi có phí mới; lịch sử lần gửi cũ và xác nhận/cảnh báo chi phí được giữ trong JSON job. Job có ID không được tạo lại bằng nút này. CLI tương đương (thay đường dẫn thật):

```powershell
.\.venv\Scripts\python.exe -m pipeline.ai_video resume 'output/<project>/ai_video/<hash>.json' --remote-id 'ID_TỪ_DASHBOARD'
```

```powershell
.\.venv\Scripts\python.exe -m pipeline.ai_video recreate 'output/<project>/ai_video/<hash>.json' --confirm-no-job --yes
```

UI và CLI mặc định tự bỏ qua Clip AI khi bước này lỗi, ghi lỗi vào `report.md` rồi render bằng b-roll gốc. Bật **Dừng pipeline khi Clip AI lỗi** hoặc dùng `--ai-on-error stop` để dừng và xử lý job. Giá trị `ask` trong checkpoint cũ được xử lý như `skip`; không chờ giữa pipeline. Có thể khôi phục job rồi thử lại riêng bước AI. Với checkpoint AI bị lỗi, tiếp tục bằng `python -m pipeline.run_all --resume 'output/<project>' --skip-ai` hoặc `--stop-ai`. Bỏ qua không hủy/hoàn tiền job đã gửi; cảnh báo được ghi vào trạng thái và báo cáo, bản dựng dùng Assets gốc, không dùng bundle AI dở dang.

Nguồn nước ngoài → kịch bản tiếng Việt: UI Research/Tạo video chọn ngôn ngữ nguồn (mặc định vi + en, hỗ trợ thêm zh/ko/ja). Đầu ra hiện chỉ hỗ trợ `vi` để giữ giọng đọc và caption tiếng Việt. Gemini sinh 2–4 truy vấn tự nhiên cho mỗi ngôn ngữ; DDGS dùng region tương ứng, lọc trang chủ/chuyên mục và ưu tiên bài cụ thể có ngày đăng. Tất cả truy vấn đã chạy được lưu trong `brief.json.search_queries` và `sources.json`; `web_limit` vẫn là tổng số nguồn đưa vào brief, được chia giữa các ngôn ngữ có kết quả.

Mỗi fact mới phải có `fact_vi` ngắn bằng tiếng Việt và `evidence_quote` nguyên văn ngôn ngữ gốc (15–200 ký tự, tối đa 25 từ). Quote được đối chiếu với văn bản nguồn gốc, không phải bản dịch; fact lỗi bị loại riêng, dưới 3 fact hợp lệ thì dừng. `source_lang`, `source_name`, `source_url`, `published_at` lấy từ nguồn; không biết ngày thì null. HTML lang được ưu tiên để xác định ngôn ngữ, nếu không có dùng ngôn ngữ truy vấn làm gợi ý. UI hiển thị song song fact_vi/quote gốc/tên báo/ngày/link nguồn.

Director chỉ nhận fact_vi và metadata nguồn, không nhận quote/claim gốc để dịch thành lời thoại. Brief tiếng Việt cũ có thể dùng claim tương thích; fact nguồn nước ngoài thiếu fact_vi phải chạy Research lại. Lời đọc dùng tên báo như “Theo Reuters”, b-roll query vẫn tiếng Anh. Có trường pronunciation_hint trong fact/cảnh để lưu ghi chú phát âm, hiển thị ở Edit Plan; không tự đưa ghi chú vào audio/caption. Không tự thêm tỷ giá, giá Việt Nam hoặc bối cảnh không có căn cứ. Credits của Assets/AI bundle và báo cáo pipeline ghi đầy đủ nguồn web, ngày và ngôn ngữ gốc, kèm nguồn chưa biết ngày.

Ví dụ chỉ nghiên cứu nguồn tiếng Anh, đầu ra tiếng Việt (chạy tại video_ai_tool):

```powershell
.\.venv\Scripts\python.exe -m agents.researcher "Dựng video cho người mới" --source-languages en --output-language vi --web-limit 3 --no-youtube
```

```powershell
.\.venv\Scripts\python.exe -m agents.director 'output/<project>/brief.json' --source-languages en --output-language vi --type review --format tiktok --duration 45
```

```powershell
.\.venv\Scripts\python.exe -m pipeline.run_all --topic "Tin công nghệ AI" --source-languages vi en ja --output-language vi --type news --format tiktok --duration 45 --review
```

Nghiên cứu sâu mặc định lấy tối đa 6 nguồn (đề xuất 5–8, đổi bằng `--web-limit` hoặc UI). Nguồn phải là bài đầy đủ trích bằng trafilatura, ít nhất 300 ký tự; nếu trích lỗi/quá ngắn thì thử lấy đoạn bài từ HTML thô đã tải, bỏ script/menu/footer, không dùng snippet và không vượt chặn 403/429. Giữ tới 8000 ký tự ở ranh giới đoạn, lưu `content_length` cùng văn bản, ưu tiên bài có ngày và các nhà xuất bản khác nhau. Cache bài cũ được tách namespace để không tái dùng snippet/nội dung đã cắt trước đây. Thiếu 5 nguồn thì cảnh báo; không tự bù bằng nguồn kém chất lượng.

Brief mới từ bài đầy đủ có `research_depth="deep"`, mục tiêu 12–20 fact khác nhau cùng quote ngắn thật; 3–5 `story_angles`. Các mục `key_numbers`, `timeline`, `why_it_matters`, `counterpoints`, `glossary` gồm `{text,fact_ids}`; không có thông tin thì mảng rỗng, không tự bịa. Khi fact bị loại, mục phụ tham chiếu fact đó cũng bị loại, các ID còn lại được đánh số lại. Fact diễn đạt 1–3 câu nhưng toàn bộ khẳng định vẫn phải được dẫn chứng hỗ trợ. Mức tối thiểu vẫn là 3 fact sau lọc; 3–7 fact sẽ hiện cảnh báo “dữ liệu mỏng, kịch bản sẽ ít chi tiết”, không ép bịa để đủ 12.

Director áp dụng kiểm tra sâu cho brief mới: mỗi cảnh body ít nhất 2 fact, mục tiêu 2.3–2.8 từ/giây với dung sai 10%, bổ sung số liệu thật vào narration, từ chối lời chung chung khi fact có số liệu. Model được yêu cầu bố cục hook/bối cảnh/3–5 ý chính/tác động/kết luận và cấu trúc ý chính–chi tiết–ý nghĩa trong cảnh. Audit tiếp tục đối chiếu ngữ nghĩa với fact_vi. Brief cũ không có research_depth vẫn mở/chỉnh sửa theo luật cũ; chạy Research và Director lại để dùng chế độ sâu. UI Research thêm bảng độ dài nguồn, số liệu/timeline; Edit Plan liệt kê nội dung các fact theo từng cảnh.

Chẩn đoán nguồn: `logs/researcher_errors.log` UTF-8 ghi số kết quả của mỗi truy vấn DDGS text/news và quyết định giữ/loại cho mỗi URL (trùng, chuyên mục, ngắn, bị chặn, lỗi tải, ngoài giới hạn). `sources.json.search_diagnostics` giữ báo cáo kể cả khi chưa có brief; UI Research hiển thị tổng tìm được/giữ/loại và bảng chi tiết. Số kết quả tính theo lượt trả về, gồm URL trùng; số nguồn giữ tính URL duy nhất đã chọn cuối cùng, nên tìm được = giữ + loại. Không có nguồn thì báo đủ số liệu và gợi ý rút gọn chủ đề/tăng số nguồn. Chủ đề liệt kê thực thể bằng dấu phẩy/chấm phẩy/và/and/vs được tách tối đa 3 nhóm cho Gemini tạo truy vấn riêng mỗi ngôn ngữ. Lỗi tìm kiếm/429 có retry chờ tăng dần và log.

Quota YouTube local: search.list = 100, videos.list/commentThreads.list = 1 đơn vị mỗi request, gồm retry thất bại; kiểm tra ngân sách trước mỗi request. Cache không tốn quota. Khi vượt YOUTUBE_DAILY_QUOTA thì chặn request, ghi cảnh báo và bỏ qua trends. Ledger cũ chưa có cost_version được nâng ước tính bảo thủ (+99 mỗi search cũ) để tránh tiếp tục dựa vào mức đếm thiếu; nếu ledger từng dùng giá cũ 100 thì có thể bị tính dư trong ngày chuyển đổi. Đây là ngân sách local, không phải số quota thực trong Google Cloud Console.

Gemini HTTP 400: giữ nguyên thông điệp API `INVALID_ARGUMENT` đã che credentials trong log và UI, không chỉ hiện “HTTP 400”. Log mỗi request ghi model, số ký tự prompt/schema, ước lượng token (`ceil(prompt_chars/3)`, không phải tokenizer chính thức), max_output_tokens và mode. Không ghi toàn bộ prompt hay nội dung cấu hình.

Researcher chia đều ngân sách tổng văn bản nguồn tối đa 40000 ký tự, ưu tiên ranh giới đoạn/từ; artifact nguồn đầy đủ giữ nguyên. Schema truyền API ở lượt 1 chỉ có facts (fact_vi/evidence_quote/source_url), góc tiếp cận và các danh sách ngắn; không có Union/Optional, metadata YouTube hay schema ResearchBrief đầy đủ. Code khôi phục metadata từ nguồn và kiểm tra grounding như trước. Lượt 2 chỉ đọc facts đã đối chiếu để tạo story_angles/timeline/key_numbers/glossary..., dùng schema riêng. Nếu lượt 2 lỗi, giữ facts cùng cảnh báo thay vì làm mất cả brief.

Khi API báo 400, không retry cùng cấu hình: thử đúng một lần với đầu vào rút ngắn (văn bản nguồn tối đa 12000 ký tự), schema nhỏ mô tả trong prompt, bỏ response_json_schema/response_mime_type/max_output_tokens/temperature/thinking config. Output vẫn phải vượt validate JSON/Pydantic/grounding tại máy. Cùng provider sẽ tiếp tục dùng mode tương thích này cho các lượt sau. Nếu lần rút gọn vẫn báo 400, dừng và hiển thị nguyên văn lỗi đã che key. Lỗi mạng/429/5xx vẫn dùng retry tạm thời riêng.

Director khi ít dữ liệu: số cảnh nội dung = max(3, min(số cảnh theo thời lượng, floor(số fact/2))); video quá ngắn để chứa 3 body vẫn giữ giới hạn shot/thời lượng vật lý. Blueprint chia shot 1.5–4 giây và tổng thời lượng chính xác. Cảnh nội dung dài có thể dùng thay đổi shot/hiệu ứng bên trong để ngắt nhịp. UI Edit Plan cảnh báo dữ liệu mỏng khi brief dưới 8 fact.

Chỉ yêu cầu 2 fact/body khi brief có đủ 2 fact mỗi body; nếu không cho phép 1 fact/body và nhắc khi một fact dùng quá 2 lần. Vi phạm số lượng/dùng lại ghi `review_notes.warnings`, không tự làm fail cả plan. Code có thể gán thêm fact chưa dùng khi thiếu; không tự thêm câu vào narration và vẫn bắt buộc audit ngữ nghĩa để tránh hợp thức hóa lời bịa bằng fact_ids.

So sánh số chuẩn hóa dấu thập phân/tiền tệ, nghìn/triệu (1M = 1 triệu = 1.000.000), phần trăm; giữ số phiên bản sản phẩm (5.5), bỏ nhãn thứ tự/cảnh và năm hiện tại. Số chưa khớp trong cảnh có fact được ghi rõ vào warnings cùng các số hợp lệ. Narration có số nhưng không fact vẫn bị chặn. Audit ngữ nghĩa không bị tắt: sai giá/đơn vị/khẳng định không có căn cứ vẫn phải sửa, không tự được thông qua chỉ vì có cảnh báo.

Retry Director chỉ thay các cảnh lỗi xác định được (JSON `{scenes:[...]}`), giữ nguyên cảnh đã đạt; lỗi toàn cục không định vị được thì kiểm tra lại cả danh sách. Tối đa 3 lần theo RETRY_ATTEMPTS. Hết lượt lưu `edit_plan.draft.json` gồm plan hiện có, warnings, failed_scene_ids và số lần thử; không ghi đè edit_plan hợp lệ cũ hoặc chạy tiếp pipeline bằng bản nháp. Trang Edit Plan có “Sửa bản nháp”; nếu JSON chưa đúng schema có ô sửa JSON, nếu đúng thì dùng trình sửa cảnh hiện có. Lưu vẫn validate và audit; thành công đánh dấu draft resolved. Log UTF-8 từng lần thử/cảnh/luật/giá trị trong `logs/director_errors.log`.

Prompt clip AI: Director/CLI `--ai-clips N` chỉ chuẩn bị N shot `ai_video` và prompt, chưa gửi tạo clip. Module `agents/video_prompt_writer.py` dùng Gemini tạo một câu tiếng Anh tối đa 30 từ, kiểm tra vốn từ an toàn, tên riêng/từ cấm, một hành động và một chuyển động camera; tối đa 2 lần viết lại rồi fallback vật thể đơn giản. AI Video và Edit Plan có trình sửa/lưu prompt từng shot, nút Viết lại prompt và tùy chọn Đơn giản hơn. Prompt sửa hợp lệ được giữ nguyên. Timeout lưu đề xuất ngắn hơn, camera tĩnh, không tự gửi lại job có phí. Đổi prompt sau lần gửi phải xác nhận tạo job mới ở AI Video, không tự POST khi resume pipeline. Prompt-only edit không yêu cầu tạo lại audio/stock; pipeline đang chạy hoặc đã render không cho sửa prompt ảnh hưởng checkpoint.


### Chẩn đoán và thử lại Clip AI

`logs/gateway_video_errors.log` (UTF-8) ghi payload thực tế đã gửi (prompt đầy đủ, model, seconds, aspect_ratio, resolution), remote ID và phản hồi lỗi đầy đủ sau khi che credentials. Trang AI Video và Tạo video hiển thị prompt/chi tiết của job lỗi; thông báo `generation_failed` chung chưa đủ xác định nguyên nhân.

Trước POST, sanitizer giữ prompt đã đạt luật hoặc thay nội dung có tên riêng/thương hiệu bằng một mô tả trung tính, một chủ thể, tối đa 30 từ tiếng Anh và camera đứng yên. Bản nháp trong Edit Plan không bị sửa.

Chỉ khi gateway xác nhận kết thúc với `generation_failed`, ứng dụng tạo tối đa **một** job mới bằng prompt dự phòng đơn giản hơn. Lần thử lại có thể tính phí; ý định thử lại được lưu trước POST và giữ qua restart/resume. Timeout, thiếu ID, HTTP 403/5xx không tạo job mới tự động. Nếu lần thử lại thất bại, pipeline dùng b-roll (trừ khi đã chọn dừng khi AI lỗi).

Cấu hình mẫu, không cần sửa key:

```dotenv
GATEWAY_VIDEO_MODEL=veo-3.1
GATEWAY_ALLOWED_MODELS=veo-3.1,seedance-2.5-30s
AI_CLIP_SECONDS=4
AI_CLIP_MAX_PER_RUN=3
```

`AI_CLIP_SECONDS` phải khớp model: Veo 4/6/8; Seedance giữ các lựa chọn 5/10/15/20–30 của gateway adapter. Khi không khai báo duration, mặc định theo model (Veo 4, Seedance 5). Cấu hình model/duration/cap không hợp lệ bị chặn khi khởi động. Cap là số clip đầu ra, mỗi clip có tối đa hai job nếu lần đầu gặp generation_failed.


### Director kể chuyện ba lượt

UI **Tạo video** và **Edit Plan** có mốc 30/60/90/120/180 giây, vẫn giữ ô tùy chỉnh cho project cũ. Bốn phong cách: kể chuyện (`storytelling`), tin nhanh (`news`), giải thích dễ hiểu (`explain`), review thẳng thắn (`review`).

Lượt mới mặc định gọi ba lượt Gemini: dàn ý có góc kể và open loop → viết theo fact IDs đã khóa → người hóa và audit căn cứ của bản cuối. Timing/shot được dựng bằng code. Lượt thứ ba kiểm tra đúng nguồn, payoff và khẳng định; code kiểm tra câu sáo rỗng, hook, câu dài, overlay, lượng chữ và nhịp cảnh. Vi phạm chỉ gửi lại các cảnh lỗi, tối đa hai lần sửa. Cache hợp lệ không gọi lại model. Các project/low-level request cũ có `script_style=null` vẫn dùng hợp đồng Director cũ.

Mục tiêu 2.4–2.8 từ/giây; 60 giây khoảng 8–10 cảnh, 90 giây 11–14, 120 giây 14–18 khi đủ fact. Dữ liệu mỏng sẽ có cảnh báo và đề xuất thời lượng ngắn hơn; ứng dụng không tự thêm sự kiện, tỷ giá hay trải nghiệm sản phẩm để kéo dài.

Trang Edit Plan có **Viết lại cảnh này** và **Viết lại toàn bộ với giọng X**. Hai thao tác dùng Gemini, giữ fact IDs; sửa riêng cảnh giữ nội dung các cảnh khác. Plan cũ còn audio/assets cần tạo lại Assets sau khi đổi narration. Kịch bản không đạt được lưu riêng trong `edit_plan.draft.json`; không ghi đè bản thành công trước đó.

```powershell
python -m agents.director "output/<project>/brief.json" --type story --format tiktok --duration 90 --style storytelling
python -m pipeline.run_all --topic "Chủ đề của bạn" --type news --format tiktok --duration 120 --style explain --review
```

Các bước cần quota hoặc có phí chỉ chạy khi bạn tự thực thi lệnh; test dùng mock.


### Khám phá chủ đề

Trang **Khám phá chủ đề** đọc RSS và bổ sung DDGS news khi ít tin. Có 9 danh mục trong `config/categories.yaml`; sửa file hoặc mở **Sửa danh mục, từ khóa và RSS** trên UI. Mỗi RSS có `region: vn/global`, `enabled`; RSS tổng hợp có thể dùng `include_keywords` để lọc đúng danh mục. Các RSS mẫu tham khảo https://vnexpress.net/rss và https://www.theguardian.com/help/feeds . Nguồn bị chặn/robots lỗi được báo riêng; không vượt chặn, không tải nội dung bài báo trong bước khám phá.

Chọn khu vực, 1/3/7 ngày và 5/10 gợi ý. Xếp hạng dùng độ mới, số nhà xuất bản độc lập và YouTube tùy chọn; YouTube tái sử dụng bộ đếm quota hiện có. Gemini chỉ chọn chủ đề từ nhóm tin, URL phải thuộc đúng nhóm, kiểm tra tên/số và loại sự kiện. Đây là gợi ý metadata, chưa phải facts: Research tiếp tục đọc và kiểm chứng bài báo. Nếu Gemini lỗi, tin thô vẫn có thể chọn tay.

Mỗi thẻ cho sửa tên, chọn vào hàng chờ hoặc mở form **Tạo video**. Chọn nhiều thẻ chỉ lưu hàng chờ, không âm thầm tạo hàng loạt. **Tự chọn chủ đề tốt nhất và tạo video** chạy top 1 chưa có project, mặc định dừng sau Director để duyệt. Clip AI luôn tắt trong thao tác tự chọn. Ô **Tự nhập chủ đề** giữ cách làm cũ.

Lịch sử `output/topics_history.json` chỉ ghi khi video hoàn tất, không ghi blacklist chỉ vì đã xem gợi ý. Chủ đề/tiêu đề tương tự hoặc cùng URL nguồn trong 14 ngày bị loại. Resume dùng project hiện có. `topic_discovery.json` trong project giữ metadata đã chọn; truy vấn vi/en được ưu tiên trong Research, góc kể chuyển vào Director làm gợi ý. Credits/report ghi các URL khám phá riêng với nguồn fact.

```powershell
python -m pipeline.discover --category "công nghệ" --region both --days 3 --count 8
python -m pipeline.discover --category "công nghệ" --region both --days 3 --count 8 --auto-pick --review
```

Lệnh thứ nhất lưu gợi ý ở `output/topics_latest.json`, chưa tạo video. Lệnh thứ hai chạy pipeline hiện có rồi chờ duyệt kịch bản. RSS, DDGS và Gemini chỉ được gọi khi bấm nút/chạy lệnh; mở trang không tự gọi mạng.


### Danh mục → Video 1 nút

Trang đầu **Tạo video theo danh mục** tự khám phá, chọn chủ đề chưa làm trong 14 ngày và gọi các module pipeline hiện có. Mặc định chạy đến bản MP4 cuối; có tùy chọn dừng sau kịch bản để duyệt. Không có nguồn dùng được hoặc không còn fact hợp lệ sẽ đổi chủ đề, tối đa ba chủ đề; lỗi quota, xác thực hoặc dựng video giữ checkpoint và báo lỗi để tiếp tục, không đổi chủ đề vô ích.

Chỉ cần một fact có bằng chứng nguyên văn; không có ngưỡng tối thiểu ba fact/hai nguồn. Thời lượng tự giảm theo lượng fact và độ dài thông tin; báo cáo ghi thời lượng yêu cầu, kế hoạch và thực tế theo audio. Mỗi cảnh phải có fact, mỗi fact dùng tối đa hai cảnh. Với đúng một fact, mở/kết được gộp trong hai cảnh để giữ giới hạn này. Mức sáng tạo strict/balanced/story chỉ đổi cách kể, không cho phép thêm sự kiện, con số hoặc nguồn. Các cảnh báo dữ liệu mỏng không chặn video.

```powershell
python -m pipeline.auto_category --category "công nghệ" --region both --days 3 --duration 60 --format tiktok
```

Thêm `--review` để duyệt; tiếp tục bằng `python -m pipeline.auto_category --resume "output/<project>"`. Thêm `--count 3` để tạo tuần tự ba video, mỗi video một project. Hàng đợi dừng khi có lỗi, hủy hoặc đang chờ duyệt. `--style storytelling|news|explain|review` và `--creative-license strict|balanced|story` điều khiển cách kể.

Clip AI mặc định tắt. UI bắt buộc xác nhận chi phí trước khi bắt đầu; CLI dùng `--ai-clips 1 --confirm-ai`. Xác nhận bao gồm khả năng thử lại một lần khi generation_failed; lỗi Clip AI luôn chuyển về b-roll thường. Resume giữ xác nhận của lượt đã lưu.

`run_state.json` giữ cả khám phá và các bước Research/Director/Assets/AI/Render, đủ để hủy ở điểm an toàn rồi tiếp tục. Bước đã hoàn tất không chạy lại nếu artifact vẫn hợp lệ. Nhật ký `logs/auto_category_errors.log` và `report.md` ghi chủ đề đã bỏ cùng lý do. Lịch sử chỉ cập nhật sau khi video hoàn tất; báo cáo có nguồn, số fact, thời lượng và ghi chú nội dung có hỗ trợ AI. Nút tạo video khác chọn chủ đề kế tiếp chưa trùng.
