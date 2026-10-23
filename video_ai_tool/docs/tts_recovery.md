# TTS và phục hồi audio từng cảnh

Assets làm sạch HTML/XML, markdown, emoji, ký tự điều khiển; chuẩn hóa khoảng trắng và giữ bước chuyển số/đơn vị/viết tắt tiếng Việt ở ranh giới TTS. `edit_plan.json` không bị sửa. Văn bản gửi dịch vụ chia theo câu, tối đa 300 ký tự/đoạn.

Mỗi đoạn có cache riêng theo văn bản đã làm sạch + giọng. Một lần gọi ban đầu, tối đa **4 lần thử lại** với khoảng chờ 2, 4, 8, 16 giây cho NoAudioReceived, lỗi mạng/WebSocket và timeout. Chỉ thử lại đoạn lỗi; tối đa 2 request đồng thời trong một tiến trình, còn pipeline duyệt cảnh tuần tự.

Hết lượt: thử giọng `DEFAULT_VOICE_FALLBACK` (mặc định `vi-VN-NamMinhNeural`), rồi văn bản bỏ thêm ký tự ngoài chữ/số/dấu câu cơ bản. Nếu vẫn lỗi, tạo MP3 im lặng theo phần thời lượng của đoạn. Văn bản rỗng/chỉ có dấu câu đi thẳng sang im lặng, không gọi Edge. Chỉ các đoạn speech thành công được cache; im lặng có thể thử lại ở lần sau.

`audio/scene_<id>.tts.json` ghi giọng thực tế, các đoạn fallback, lỗi và cảnh báo. `assets.json` có `audio_silent`, `audio_error`, `audio_voice`, `audio_warnings` từng cảnh. Im lặng là audio có thật, cho phép render nhưng UI/report ghi rõ **cảnh N không có giọng đọc**; captions vẫn xuất hiện ở cảnh đó kể cả preset tắt phụ đề. Lỗi không ghi được audio/im lặng do ổ đĩa/FFmpeg vẫn dừng với thông báo TTS đúng cảnh.

Log UTF-8: `logs/assets_errors.log`, gồm cảnh, đoạn, số lần thử, giọng, số ký tự và tối đa 200 ký tự văn bản đã làm sạch; credentials được che.

Chạy lại **riêng audio cảnh 2** từ thư mục dự án:

```powershell
.\.venv\Scripts\python.exe -m pipeline.assets "output/auto-cong-nghe-c8813fcb/edit_plan.json" --scene 2
```

Hoặc **Assets → chọn cảnh → Chạy lại riêng audio cảnh N**. Không tìm/tải lại stock, không tạo lại audio các cảnh khác. Clip sẵn có được dùng lại theo timing mới; các cảnh bị lệch timing do bản cũ được sửa metadata theo audio thật, không gọi thêm API. Bước này không render video.

Assets chỉ cảnh báo nếu thời lượng audio khác mục tiêu quá 10%; không gọi bộ sửa thời lượng của Director trên resolved plan. Nhờ đó số shot manifest luôn khớp resolved plan sau khi retime theo audio.

Kiểm thử offline:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp -p no:cacheprovider
```
