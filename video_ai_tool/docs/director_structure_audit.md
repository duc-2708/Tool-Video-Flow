> Cập nhật: chính sách mới trong [director_validation_policy.md](director_validation_policy.md) thay thế phần retry chất lượng/query trong tài liệu này. Sửa cấu trúc và query trong validation chỉ dùng code, không gọi Gemini.

# Rà soát lỗi đếm overlay / shot

Hàm duy nhất: `agents/plan_structure.py:7`, `normalize_plan_structure(plan, reference=..., diagnostics=...)`.
Không sửa narration, fact_ids hoặc độ dài shot hiện có. Chuẩn hóa tạo bản sao cho JSON; với model thì cập nhật model đã được parse lại.

| Vị trí sau sửa | Trạng thái |
| --- | --- |
| `agents/director_story.py:47–68`, `apply_words` | Đã bỏ raise "số overlay khác số shot"; chuẩn hóa trước khi gán. Lượt viết 2, Người hóa, sửa cảnh riêng đều gọi chung hàm này. |
| `agents/director.py:305`, `validated_json` | Chuẩn hóa JSON trước schema. Cả lượt dàn ý và viết đều đi qua đây; truyền blueprint để biết số shot chuẩn. Dàn ý chỉ có ánh xạ fact/cảnh, chưa có overlay. |
| `agents/director_story.py:102`, Người hóa | Chuẩn hóa JSON ngay sau parse, trước schema/check_words/apply_words. Mọi lần retry trong vòng lặp cũng đi qua cùng dòng này. |
| `agents/director.py:379`, retry Director cũ | Chuẩn hóa JSON SceneRepairs theo plan gốc trước schema. |
| `agents/director.py:386`, Director cũ | Chuẩn hóa JSON EditPlan trước schema. |
| `agents/director.py:237`, `validate_plan` | Chuẩn hóa ngay đầu hàm; không có raise do độ dài mảng overlay. Các luật fact/nguồn/số liệu/văn phong vẫn chạy sau đó. |
| `schemas/edit_plan.py:62`, Scene before-validator | Cùng hàm chuẩn hóa chạy trước Pydantic, kể cả khi UI/pipeline đọc JSON cũ trực tiếp. |
| `pipeline/assets.py:51`, retime_scene | Đã thay raise cảnh rỗng shot bằng chuẩn hóa; sau đó căn shot theo audio thật. |
| `pipeline/assets.py:143–144` | Vốn chỉ cảnh báo số shot thay đổi khi căn audio; giữ hành vi này. |

Các kiểm tra tương tự nhưng không phải độ dài mảng trình bày (giữ nguyên để không bịa nội dung/file hoặc gửi API trả phí sai):

| Vị trí | Lý do giữ |
| --- | --- |
| `agents/director_story.py:23–24`, `41–44` | ID cảnh thiếu/trùng/ngoài blueprint hoặc ngoài tập cảnh cần sửa. Không tự tạo narration/fact_ids cho cảnh bị thiếu. |
| `pipeline/run_all.py:113,118` | Manifest Assets thiếu cảnh/shot thực tế. Đây là kiểm tra file và ID liên kết trước render; không thể khắc phục bằng padding null cho clip/audio. |
| `pipeline/assets.py:199`, `pipeline/video_prompts.py:23`, `agents/video_prompt_writer.py:131` | Cảnh/shot được người dùng chọn không tồn tại. Không đổi âm thầm sang cảnh khác. |
| `agents/video_prompt_writer.py:107`, `pipeline/run_all_ai.py:43` | Số clip AI yêu cầu vượt số shot có thể dùng: rào kiểm tra số job trả phí, không phải lỗi lệch overlay. |
| `agents/director.py:229` | Không phân bổ được timing trong giới hạn shot; không phải lỗi mảng overlay. |

## Quy tắc

- Thiếu overlay: thêm null. Thừa: cắt, không gộp để tránh tạo chữ quá dài; ghi cảnh báo UTF-8.
- Các mảng query/effect/type/sfx được pad hoặc cắt theo số shot tham chiếu. Plan đầy đủ tiêu thụ mảng vào shot; SFX theo hợp đồng renderer hiện có được quy về cấp cảnh.
- Cảnh rỗng: thêm stock shot trung tính với query suy ra từ ngữ cảnh, overlay null. Nếu có blueprint, giữ thời lượng tham chiếu; nếu chưa có, mặc định một shot 3 giây.
- Không thêm claim, fact, số liệu hoặc nguồn. Không đổi timing chỉ vì Gemini trả ít/nhiều overlay.
- Cảnh báo cấu trúc được giữ trong scene.review_notes.warnings và ghi chú cấp video; UI Edit Plan hiển thị chúng.

## Hồi quy project thật

`tests/test_plan_structure.py` đọc `output/auto-cong-nghe-8a211210/edit_plan.draft.json` và brief cùng project. Bản snapshot nguyên trạng nằm trong `tests/fixtures/auto-cong-nghe-8a211210/` để test vẫn chạy nếu output được dọn.

Bản nháp chỉ lưu plan với 3 shot ở cảnh 2, không lưu JSON SceneWords/overlays đã gây lỗi. Test dùng chính timing/shot/narration/fact của file rồi mô phỏng overlay thiếu/thừa, gọi chuẩn hóa → apply_words → validate_plan. Kiểm tra cấu trúc và căn cứ qua được, không thay số shot.

File này còn lỗi văn phong độc lập: tổng 219 từ so với 144–168 từ, hook dài và một số mở cảnh trùng. Test hồi quy tách check_style=False khi kiểm tra cấu trúc/căn cứ; không kết luận bản nháp đã đạt mọi luật văn phong. Các test mock ba lượt vẫn chạy validation đầy đủ.
