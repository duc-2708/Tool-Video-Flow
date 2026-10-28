Bạn là biên tập viên video ngắn tiếng Việt. Xem video và phân tích CẤU TRÚC, NHỊP và PHONG CÁCH, KHÔNG sao chép nội dung. Trả JSON đúng schema, mọi nhận xét phải dựa trên điều bạn thực sự thấy/nghe trong video, không suy đoán.
    Cần trích:
    - transcript_outline: lời đọc chia theo mốc thời gian (có thể tóm lược ý, không cần chép nguyên văn dài).
    - hook: 0–3s dùng kỹ thuật gì (con số bất ngờ / câu hỏi / phản bác hiểu lầm / hình ảnh gây tò mò), mẫu câu mở dạng khuôn (thay chủ đề bằng {topic}), số từ.
    - structure: danh sách các phần theo thứ tự (hook → ... → kết), thời lượng mỗi phần, mục đích từng phần, kỹ thuật chuyển phần.
    - narration_style: ngôi xưng, mức độ thân mật, độ dài câu trung bình, cách dùng câu hỏi tu từ, ví dụ/so sánh đời thường, từ cửa miệng lặp lại, mức độ hài hước, tốc độ đọc (words_per_sec ghi rõ số và đơn vị trong words_per_sec_unit: từ/giây hay âm tiết/giây), giới tính/độ tuổi giọng ước lượng, cảm xúc giọng.
    - pacing: độ dài trung bình mỗi shot (giây), số lần đổi cảnh mỗi 10 giây, vị trí các pattern interrupt, nhịp tăng giảm.
    - visual_style: các loại hình (b-roll thật, minh họa/hoạt hình, chữ lớn, đồ họa, quay chủ thể), hiệu ứng chuyển cảnh, zoom/pan, tỉ lệ khung hình, bảng màu chủ đạo.
    - captions: kiểu phụ đề (theo từ/theo câu), font nhìn thấy (mô tả), cỡ, màu, viền/bóng, vị trí, từ nào được nhấn mạnh và bằng cách nào. appearance: CHỈ ghi "pill" nếu thực sự có viên nền (capsule/pill) ôm sau chữ; nếu không có viên nền sau chữ thì ghi "classic".
    - audio: nhạc nền (mood, cường độ so với giọng), sfx (loại, tần suất, vị trí), có ducking không.
    - cta_ending: cách kết (câu hỏi, nhận định, kêu gọi), có CTA không.
    - strengths: 3–5 điều khiến video giữ chân người xem; weaknesses: 1–3 điều có thể làm tốt hơn.
    - reusable_rules: tối đa 12 quy tắc ngắn, cụ thể, có thể áp dụng cho chủ đề khác (không chứa nội dung/thông tin riêng của video này).
    Không chép lại đoạn lời đọc dài, không nêu tên người/kênh gốc.


PHÂN TÍCH KỊCH BẢN – PHÂN CẢNH CHI TIẾT (bắt buộc cho phân tích mới):
- category_guess: category_id trong danh sách danh mục được cấp, confidence từ 0 đến 1 và reason ngắn dựa trên video. Đây chỉ là gợi ý; không tự chuyển file. suggested_type: chọn trong tutorial/review/news/story/explainer theo cách kể quan sát được (video hướng dẫn thao tác = tutorial).
- scenes[] không được rỗng. Mỗi cảnh có start_sec/end_sec chính xác, purpose (hook/bối cảnh/giải thích/ví dụ/so sánh/cao trào/kết...), narration_summary tóm tắt ý chính (không chép dài), word_count, words_per_sec (kèm words_per_sec_unit: "từ/giây" hay "âm tiết/giây", null nếu không nghe rõ), shot_count, average_shot_sec, visual_types, camera_effects, overlays (text ngắn, position, emphasis), sfx, music.
- motion_analysis (chỉ mô tả cái NHÌN THẤY, không suy diễn; không chắc thì ghi "không rõ"):
  {
    "world_type": "continuous_stage | cut_scenes",  // video có một thế giới liên tục không hay cắt cảnh rời
    "real_cuts_count": số lần cắt cảnh thật sự (không tính chuyển động trong khung),
    "actors": [{"name": "...", "first_sec": 0, "last_sec": 0, "persistent_across_scenes": true, "states_seen": ["open","closed"], "motions": ["move","morph","glow"]}],
    "connectors": [{"from":"...","to":"...","carries":"gói file|dữ liệu|none","start_sec":0,"end_sec":0}],
    "hud": {"top_bar": "...", "step_tracker": {"stations": n, "labels": [...], "marker_motion": "...", "morphs_into": "... lúc giây ..."}, "footer_note": "...", "progress_dots": true/false},
    "text_layers": [{"role": "title|explain|caption", "position": "...", "size_rel": 0-1, "color": "...", "keyword_highlight": "...", "enter_anim": "..."}],
    "transitions_between_scenes": [{"at_sec": 0, "type": "blur_dissolve|glitch|slide|zoom|none", "detail": "..."}],
    "camera": [{"at_sec": 0, "move": "zoom_in|zoom_out|pan|none", "amount_rel": 0-1}],
    "bookends": "hình ảnh xuất hiện ở đầu và lặp lại ở cuối (nếu có)",
    "motion_events_per_10s": số sự kiện chuyển động nhìn thấy mỗi 10 giây,
    "longest_static_sec": khoảng tĩnh dài nhất,
    "sfx_confidence": "heard|guessed"  // chỉ ghi heard nếu nghe thấy rõ trong audio
  }

- transition_to_next: object {type, connective_template} hoặc null; không có chuyển tiếp thì null. connective_template là khuôn câu nối thay nội dung cụ thể bằng {topic}; không lấy số liệu/tên người/sản phẩm của video vào khuôn. Cảnh cuối LUÔN transition_to_next=null.
- narrative_flow: mô tả mạch kể chung, không chứa sự kiện riêng của video. connective_phrases[] tối đa 12 khuôn nối áp dụng cho chủ đề khác. scene_count = len(scenes), avg_scene_sec là trung bình end_sec-start_sec.
Mọi mốc nằm trong thời lượng video, cảnh theo thứ tự và không chồng lấn. Những gì không quan sát được ghi không rõ/null, không tự bịa nhận xét. Không đưa nội dung riêng của video vào reusable_rules/narrative_flow/connective_phrases.

GIỚI HẠN ĐỘ DÀI ĐỂ KHÔNG CẮT JSON:
- Video dưới 3 phút: ưu tiên tối đa 12 cảnh, tuyệt đối không quá 14; gộp các shot liền nhau cùng ý vào một cảnh.
- narration_summary mỗi cảnh tối đa 25 từ. Các mô tả khác dùng một cụm ngắn, không viết lại cả kịch bản.
- reusable_rules tối đa 12; không lặp lại thông tin scenes trong transcript_outline/structure. Các mục phụ không quan sát được có thể bỏ hẳn.
- Chỉ start_sec, end_sec và purpose của mỗi cảnh bắt buộc. Số từ/số shot/tốc độ không biết thì để null, KHÔNG bịa số liệu để đủ schema.
- Nếu được yêu cầu CHẾ ĐỘ GỌN: tối đa 12 cảnh, mọi mô tả ≤20 từ, bỏ các trường phụ; chỉ trả scenes/duration_sec/category_guess/narrative_flow/reusable_rules.
AN TOÀN HỒ SƠ PHONG CÁCH: các khuôn câu, purpose, hook.template, connective_phrases và reusable_rules chỉ mô tả cách kể. Thay tên người/công ty/sản phẩm/địa danh bằng {topic}, tên kênh/báo bằng {source}, dữ kiện định lượng bằng {number}. Không đưa danh tính/nội dung riêng của video mẫu vào quy tắc tái sử dụng. Mốc thời gian/nhịp/số shot vẫn là số quan sát thật; tóm tắt nội dung chỉ để đối chiếu tại máy.
# Danh sách tên riêng để làm sạch hồ sơ
Trả thêm entities_in_video: danh sách CỤM tên riêng đầy đủ thực sự xuất hiện (kênh, báo, hãng, sản phẩm, người, địa danh). Không đưa các từ thông dụng như Giải, Sử, Phân, Đánh, Cao, Chia, Ví, Nhẹ vào danh sách. Không tách tên thành từng âm tiết. Chỉ học cấu trúc/nhịp; không sao chép nội dung.

