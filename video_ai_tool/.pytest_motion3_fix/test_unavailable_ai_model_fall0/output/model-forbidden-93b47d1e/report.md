# Báo cáo: Model forbidden
Trạng thái: done
Fact trong brief: 3; fact dùng trong kịch bản: 1; nguồn fact đã dùng: 1.
Thời gian xử lý: 0.47 giây.

## Các bước
- Research: done · 0.06s
- Kịch bản: done · 0.12s
- Assets: done · 0.19s
- Clip AI: skipped · 0.01s
- Render: done · 0.08s

## Nguồn fact đã dùng
- https://example.com/

## Thời lượng
Yêu cầu 45s; kế hoạch 45.0s; thực tế 45.0s.

## Nguồn đối chiếu trong brief
- https://example.com/
- https://example.com/
- https://example.com/

## Cảnh báo
- Cảnh báo nguồn fixture
- [attribution, nhóm 2, fixed] Đã đồng bộ cách nêu nguồn với metadata brief, không thêm claim.
- [fact_reuse, nhóm 2, fixed] Đã khử ID trùng, ưu tiên fact tương đương; gộp cảnh 5 → 6, giữ shot/thời lượng và các khẳng định có căn cứ.
- [hook_strength, nhóm 3, warning] Hook cần câu hỏi, con số hoặc mâu thuẫn có căn cứ.
- Cảnh 2, shot 1: sửa b-roll query 'video editing' → 'video editing aerial'
- Cảnh 2, shot 2: sửa b-roll query 'video editing' → 'video editing wide'
- [presentation_voice, nhóm 3, warning] Có 2 cụm có thể/có lẽ/dường như trong 2 cảnh; tối đa 1 mỗi 2 cảnh, giữ mềm nếu là ước đoán.
- [sentence_length, nhóm 3, warning] Cảnh cần 2–4 câu, ý chính rồi chi tiết và câu dẫn.
- [transitions, nhóm 3, warning] Hai cảnh liên tiếp mở bằng cùng cấu trúc.
- [repeated_ideas, nhóm 3, warning] Lặp nguyên ý/lời cảnh khác; giảm thời lượng hoặc thêm fact thật.
- [word_budget, nhóm 3, warning] Tổng 60 từ; mục tiêu 117 ±20%, chỉ thêm chi tiết có fact.
- [word_budget, nhóm 3, warning] Lượng chữ của cảnh lệch thời lượng; phân bổ lại bằng chi tiết từ fact, không lặp ý.
- [broll_query, nhóm 2, fixed] Cảnh 2, shot 1: sửa b-roll query 'video editing' → 'video editing aerial'
- [broll_query, nhóm 2, fixed] Cảnh 2, shot 2: sửa b-roll query 'video editing' → 'video editing wide'
- Cảnh 3, shot 1: sửa b-roll query 'video editing' → 'video editing closeup'
- Cảnh 3, shot 2: sửa b-roll query 'video editing' → 'video editing interior'
- [broll_query, nhóm 2, fixed] Cảnh 3, shot 1: sửa b-roll query 'video editing' → 'video editing closeup'
- [broll_query, nhóm 2, fixed] Cảnh 3, shot 2: sửa b-roll query 'video editing' → 'video editing interior'
- Cảnh 4, shot 1: sửa b-roll query 'video editing' → 'video editing exterior'
- Cảnh 4, shot 2: sửa b-roll query 'video editing' → 'video editing panoramic'
- [broll_query, nhóm 2, fixed] Cảnh 4, shot 1: sửa b-roll query 'video editing' → 'video editing exterior'
- [broll_query, nhóm 2, fixed] Cảnh 4, shot 2: sửa b-roll query 'video editing' → 'video editing panoramic'
- Cảnh 6, shot 1: sửa b-roll query 'video editing' → 'video editing aerial night'
- Cảnh 6, shot 2: sửa b-roll query 'video editing' → 'video editing aerial daylight'
- [broll_query, nhóm 2, fixed] Cảnh 6, shot 1: sửa b-roll query 'video editing' → 'video editing aerial night'
- [broll_query, nhóm 2, fixed] Cảnh 6, shot 2: sửa b-roll query 'video editing' → 'video editing aerial daylight'
- Cảnh 7, shot 1: sửa b-roll query 'video editing' → 'video editing aerial sunset'
- Cảnh 7, shot 2: sửa b-roll query 'video editing' → 'video editing aerial sunrise'
- [broll_query, nhóm 2, fixed] Cảnh 7, shot 1: sửa b-roll query 'video editing' → 'video editing aerial sunset'
- [broll_query, nhóm 2, fixed] Cảnh 7, shot 2: sửa b-roll query 'video editing' → 'video editing aerial sunrise'
- Cảnh 8, shot 1: sửa b-roll query 'video editing' → 'video editing aerial view'
- Cảnh 8, shot 2: sửa b-roll query 'video editing' → 'video editing aerial daytime'
- [broll_query, nhóm 2, fixed] Cảnh 8, shot 1: sửa b-roll query 'video editing' → 'video editing aerial view'
- [broll_query, nhóm 2, fixed] Cảnh 8, shot 2: sửa b-roll query 'video editing' → 'video editing aerial daytime'
- Fallback fixture
- Bước Clip AI lỗi: Model seedance-2.5 không được phép trong GATEWAY_ALLOWED_MODELS. Model hợp lệ: veo-3.1, seedance-2.5-30s. Kiểm tra quyền model của key gateway. · Job đã gửi có thể vẫn tính phí; bỏ qua không hủy job.

## Tự sửa và cảnh báo Director
- Cảnh 2 · presentation_voice · nhóm 3 · warning: Có 2 cụm có thể/có lẽ/dường như trong 2 cảnh; tối đa 1 mỗi 2 cảnh, giữ mềm nếu là ước đoán.
- Cảnh 3 · presentation_voice · nhóm 3 · warning: Có 2 cụm có thể/có lẽ/dường như trong 2 cảnh; tối đa 1 mỗi 2 cảnh, giữ mềm nếu là ước đoán.
- Cảnh 4 · presentation_voice · nhóm 3 · warning: Có 2 cụm có thể/có lẽ/dường như trong 2 cảnh; tối đa 1 mỗi 2 cảnh, giữ mềm nếu là ước đoán.
- Cảnh 5 · presentation_voice · nhóm 3 · warning: Có 2 cụm có thể/có lẽ/dường như trong 2 cảnh; tối đa 1 mỗi 2 cảnh, giữ mềm nếu là ước đoán.
- Cảnh 6 · presentation_voice · nhóm 3 · warning: Có 2 cụm có thể/có lẽ/dường như trong 2 cảnh; tối đa 1 mỗi 2 cảnh, giữ mềm nếu là ước đoán.
- Cảnh 7 · presentation_voice · nhóm 3 · warning: Có 2 cụm có thể/có lẽ/dường như trong 2 cảnh; tối đa 1 mỗi 2 cảnh, giữ mềm nếu là ước đoán.
- Cảnh 1 · attribution · nhóm 2 · fixed: Đã đồng bộ cách nêu nguồn với metadata brief, không thêm claim.
- Cảnh 2 · attribution · nhóm 2 · fixed: Đã đồng bộ cách nêu nguồn với metadata brief, không thêm claim.
- Cảnh 3 · attribution · nhóm 2 · fixed: Đã đồng bộ cách nêu nguồn với metadata brief, không thêm claim.
- Cảnh 4 · attribution · nhóm 2 · fixed: Đã đồng bộ cách nêu nguồn với metadata brief, không thêm claim.
- Cảnh 5 · attribution · nhóm 2 · fixed: Đã đồng bộ cách nêu nguồn với metadata brief, không thêm claim.
- Cảnh 6 · attribution · nhóm 2 · fixed: Đã đồng bộ cách nêu nguồn với metadata brief, không thêm claim.
- Cảnh 7 · attribution · nhóm 2 · fixed: Đã đồng bộ cách nêu nguồn với metadata brief, không thêm claim.
- Cảnh 1 · fact_reuse · nhóm 2 · fixed: Đã khử ID trùng, ưu tiên fact tương đương; gộp cảnh 5 → 6, giữ shot/thời lượng và các khẳng định có căn cứ.
- Cảnh 2 · fact_reuse · nhóm 2 · fixed: Đã khử ID trùng, ưu tiên fact tương đương; gộp cảnh 5 → 6, giữ shot/thời lượng và các khẳng định có căn cứ.
- Cảnh 3 · fact_reuse · nhóm 2 · fixed: Đã khử ID trùng, ưu tiên fact tương đương; gộp cảnh 5 → 6, giữ shot/thời lượng và các khẳng định có căn cứ.
- Cảnh 4 · fact_reuse · nhóm 2 · fixed: Đã khử ID trùng, ưu tiên fact tương đương; gộp cảnh 5 → 6, giữ shot/thời lượng và các khẳng định có căn cứ.
- Cảnh 5 · fact_reuse · nhóm 2 · fixed: Đã khử ID trùng, ưu tiên fact tương đương; gộp cảnh 5 → 6, giữ shot/thời lượng và các khẳng định có căn cứ.
- Cảnh 6 · fact_reuse · nhóm 2 · fixed: Đã khử ID trùng, ưu tiên fact tương đương; gộp cảnh 5 → 6, giữ shot/thời lượng và các khẳng định có căn cứ.
- Cảnh 7 · fact_reuse · nhóm 2 · fixed: Đã khử ID trùng, ưu tiên fact tương đương; gộp cảnh 5 → 6, giữ shot/thời lượng và các khẳng định có căn cứ.
- Cảnh 1 · hook_strength · nhóm 3 · warning: Hook cần câu hỏi, con số hoặc mâu thuẫn có căn cứ.
- Cảnh 2 · sentence_length · nhóm 3 · warning: Cảnh cần 2–4 câu, ý chính rồi chi tiết và câu dẫn.
- Cảnh 3 · sentence_length · nhóm 3 · warning: Cảnh cần 2–4 câu, ý chính rồi chi tiết và câu dẫn.
- Cảnh 4 · sentence_length · nhóm 3 · warning: Cảnh cần 2–4 câu, ý chính rồi chi tiết và câu dẫn.
- Cảnh 6 · sentence_length · nhóm 3 · warning: Cảnh cần 2–4 câu, ý chính rồi chi tiết và câu dẫn.
- Cảnh 7 · sentence_length · nhóm 3 · warning: Cảnh cần 2–4 câu, ý chính rồi chi tiết và câu dẫn.
- Cảnh 8 · sentence_length · nhóm 3 · warning: Cảnh cần 2–4 câu, ý chính rồi chi tiết và câu dẫn.
- Cảnh 2 · transitions · nhóm 3 · warning: Hai cảnh liên tiếp mở bằng cùng cấu trúc.
- Cảnh 3 · transitions · nhóm 3 · warning: Hai cảnh liên tiếp mở bằng cùng cấu trúc.
- Cảnh 4 · transitions · nhóm 3 · warning: Hai cảnh liên tiếp mở bằng cùng cấu trúc.
- Cảnh 6 · transitions · nhóm 3 · warning: Hai cảnh liên tiếp mở bằng cùng cấu trúc.
- Cảnh 7 · transitions · nhóm 3 · warning: Hai cảnh liên tiếp mở bằng cùng cấu trúc.
- Cảnh 2 · repeated_ideas · nhóm 3 · warning: Lặp nguyên ý/lời cảnh khác; giảm thời lượng hoặc thêm fact thật.
- Cảnh 3 · repeated_ideas · nhóm 3 · warning: Lặp nguyên ý/lời cảnh khác; giảm thời lượng hoặc thêm fact thật.
- Cảnh 4 · repeated_ideas · nhóm 3 · warning: Lặp nguyên ý/lời cảnh khác; giảm thời lượng hoặc thêm fact thật.
- Cảnh 6 · repeated_ideas · nhóm 3 · warning: Lặp nguyên ý/lời cảnh khác; giảm thời lượng hoặc thêm fact thật.
- Cảnh 7 · repeated_ideas · nhóm 3 · warning: Lặp nguyên ý/lời cảnh khác; giảm thời lượng hoặc thêm fact thật.
- Cảnh 2 · word_budget · nhóm 3 · warning: Tổng 60 từ; mục tiêu 117 ±20%, chỉ thêm chi tiết có fact.
- Cảnh 2 · word_budget · nhóm 3 · warning: Lượng chữ của cảnh lệch thời lượng; phân bổ lại bằng chi tiết từ fact, không lặp ý.
- Cảnh 3 · word_budget · nhóm 3 · warning: Tổng 60 từ; mục tiêu 117 ±20%, chỉ thêm chi tiết có fact.
- Cảnh 3 · word_budget · nhóm 3 · warning: Lượng chữ của cảnh lệch thời lượng; phân bổ lại bằng chi tiết từ fact, không lặp ý.
- Cảnh 4 · word_budget · nhóm 3 · warning: Tổng 60 từ; mục tiêu 117 ±20%, chỉ thêm chi tiết có fact.
- Cảnh 4 · word_budget · nhóm 3 · warning: Lượng chữ của cảnh lệch thời lượng; phân bổ lại bằng chi tiết từ fact, không lặp ý.
- Cảnh 6 · word_budget · nhóm 3 · warning: Tổng 60 từ; mục tiêu 117 ±20%, chỉ thêm chi tiết có fact.
- Cảnh 6 · word_budget · nhóm 3 · warning: Lượng chữ của cảnh lệch thời lượng; phân bổ lại bằng chi tiết từ fact, không lặp ý.
- Cảnh 7 · word_budget · nhóm 3 · warning: Tổng 60 từ; mục tiêu 117 ±20%, chỉ thêm chi tiết có fact.
- Cảnh 7 · word_budget · nhóm 3 · warning: Lượng chữ của cảnh lệch thời lượng; phân bổ lại bằng chi tiết từ fact, không lặp ý.
- Cảnh 8 · word_budget · nhóm 3 · warning: Tổng 60 từ; mục tiêu 117 ±20%, chỉ thêm chi tiết có fact.
- Cảnh 8 · word_budget · nhóm 3 · warning: Lượng chữ của cảnh lệch thời lượng; phân bổ lại bằng chi tiết từ fact, không lặp ý.
- Cảnh 2 · broll_query · nhóm 2 · fixed: Cảnh 2, shot 1: sửa b-roll query 'video editing' → 'video editing aerial'
- Cảnh 2 · broll_query · nhóm 2 · fixed: Cảnh 2, shot 2: sửa b-roll query 'video editing' → 'video editing wide'
- Cảnh 3 · broll_query · nhóm 2 · fixed: Cảnh 3, shot 1: sửa b-roll query 'video editing' → 'video editing closeup'
- Cảnh 3 · broll_query · nhóm 2 · fixed: Cảnh 3, shot 2: sửa b-roll query 'video editing' → 'video editing interior'
- Cảnh 4 · broll_query · nhóm 2 · fixed: Cảnh 4, shot 1: sửa b-roll query 'video editing' → 'video editing exterior'
- Cảnh 4 · broll_query · nhóm 2 · fixed: Cảnh 4, shot 2: sửa b-roll query 'video editing' → 'video editing panoramic'
- Cảnh 6 · broll_query · nhóm 2 · fixed: Cảnh 6, shot 1: sửa b-roll query 'video editing' → 'video editing aerial night'
- Cảnh 6 · broll_query · nhóm 2 · fixed: Cảnh 6, shot 2: sửa b-roll query 'video editing' → 'video editing aerial daylight'
- Cảnh 7 · broll_query · nhóm 2 · fixed: Cảnh 7, shot 1: sửa b-roll query 'video editing' → 'video editing aerial sunset'
- Cảnh 7 · broll_query · nhóm 2 · fixed: Cảnh 7, shot 2: sửa b-roll query 'video editing' → 'video editing aerial sunrise'
- Cảnh 8 · broll_query · nhóm 2 · fixed: Cảnh 8, shot 1: sửa b-roll query 'video editing' → 'video editing aerial view'
- Cảnh 8 · broll_query · nhóm 2 · fixed: Cảnh 8, shot 2: sửa b-roll query 'video editing' → 'video editing aerial daytime'

## Clip AI đã dùng

## Video
C:\Users\admin\Desktop\app create video\video_ai_tool\.pytest_motion3_fix\test_unavailable_ai_model_fall0\output\model-forbidden-93b47d1e\render\fixture_preview.mp4

NGUỒN NGHIÊN CỨU — ngôn ngữ gốc; ngày xuất bản
- Fixture | https://example.com/ | Không rõ ngày | ngôn ngữ gốc: vi
