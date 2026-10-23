# Explainer v2

Chế độ mới được chọn bằng checkbox Explainer v2 ở Research, Edit Plan, Tạo video
và Tạo video theo danh mục; CLI thêm `--explainer-v2`. Mặc định cũ vẫn giữ
`content_mode=event_only` để không đổi nghĩa checkpoint/Assets đang dùng.

## Ranh giới nội dung

`Scene.sentences[]` gồm `type`, `text`, `fact_ids`. `narration` là phép nối
chính xác các câu này, không phải một bản lời đọc độc lập.

- `event`: số, tên, ngày, phát ngôn của sự kiện phải có trong brief; mỗi câu
  cần fact_ids hợp lệ. Giữ kiểm tra số, tên, nguồn, trích dẫn hiện có.
- `explain`: khái niệm, cơ chế, ẩn dụ nền có độ mềm. Không bắt có fact_id.
- `opinion`: nhận định có dấu hiệu chủ quan/điều kiện, không giả làm sự kiện.
- `cta`: lời mời/câu hỏi, không nhét dữ kiện mới.

Luật nhóm 1 `sentence_grounding` ngăn đổi nhãn để lách kiểm chứng: số liệu gắn
với công ty/người, ngày/phát ngôn riêng phải là event. Số nền cần từ ước lượng,
làm tròn và không gắn với thực thể sự kiện. Tên riêng ngoài brief trong event
được thử sửa riêng câu một lần bằng fact có căn cứ, chưa sửa được mới chặn.
Tên riêng trong explain/opinion/cta chỉ cảnh báo nhóm 3; từ tiếng Việt thông
dụng viết hoa đầu câu không được coi là tên riêng. Đồ họa dùng cùng bộ dò và
nhãn câu, Render thay thẻ event sai bằng bản trung tính thay vì dừng video.
Không cam kết kiến thức nền có độ chính xác 70–75%; chỉ cho phép diễn giải mềm
và đánh dấu rõ nguồn tri thức. `knowledge_notes` không được nhập vào `facts`.

## Research

Gemini sinh câu hỏi và query vi/en cho từng câu; các ngôn ngữ khác dùng bộ query
hiện có. Tìm bài phân tích cụ thể. Live blog đứng sau bài thường và bị loại
khỏi đầu vào nếu đã có bài cụ thể; nếu chỉ còn live blog thì cảnh báo nguồn
nhiều tin lẫn lộn. Nguồn vẫn tải, kiểm tra quote gốc, lọc fact như trước.
Sau grounding, Gemini viết tối đa 8 knowledge_notes (low/medium, source là
`kiến thức nền`, có ẩn dụ); không biến kiến thức nền thành fact sự kiện.

## Director

Checkpoint mới `director_state.explainer_v2.json` giữ outline, written,
humanized, final. Không ghi đè checkpoint cũ. Dàn ý 5–7 beat cho khoảng 60s,
150–180 từ; mỗi beat có information_kind và new_information.
Script critic chấm 5 tiêu chí 1–5, điểm dưới 3 đề nghị sửa đúng cảnh yếu,
tối đa một vòng. Lỗi critic chỉ cảnh báo, giữ bản đã qua kiểm tra.

Open loop dùng lượt Gemini nhỏ so câu hỏi với **lời kết thật**. Nếu chưa trả lời,
thử câu hỏi mới một lần và kiểm tra lại; nếu không xác nhận được thì bỏ câu hỏi.
Không dùng thuật toán tự nhét fact vào cảnh cuối. Không dùng fact_ids làm bằng
chứng rằng câu hỏi đã được trả lời.

Thời lượng theo lời đọc, shot 2.5–4s, không giới hạn bốn shot/cảnh như mode cũ.
Query b-roll theo ý từng câu, không thêm hậu tố máy quay để giả khác nhau.
Khi chỉ có một ý hình ảnh, giữ query và đổi phần tử đồ họa thay vì bịa ý mới.
Nguồn dùng thẻ đầu/cuối, không thêm `Theo ...` vào từng cảnh. Tiêu đề Việt <=60 ký tự.

## So sánh Barclays, không sửa bản cũ

```
python -m pipeline.explainer_compare output/auto-cong-nghe-57970c7e --duration 60
```

Lệnh đọc checkpoint ba lượt cũ, chỉ lấy kịch bản/dàn ý của project (không gửi
reference_texts của video mẫu), tạo project riêng, giữ `edit_plan.before.json`
và `director_state.legacy.json`, tạo `comparison.md` và plan mới. Lệnh gọi Gemini
để viết/critic; không tạo audio, clip AI hay video. Resume checkpoint v2 bằng
`python -m agents.director <brief mới> --explainer-v2 --duration 60`.
