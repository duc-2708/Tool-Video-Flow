with open('docs/PROCESS.md', 'r', encoding='utf-8') as f:
    text = f.read()

entry_sec2 = '''| 2026-10-29 | Ưu tiên tuyệt đối - Chống bịa số & Nối Motion Vocabulary vào pipeline: (1) Phân tích và triệt phá nguyên nhân gốc sinh số bịa: renderBarCompare tự sinh 0.45/'Ước tính', renderStatNumber sinh 0.5, renderVersusSplit sinh 40%/85%, lineChartDraw sinh 4 tháng giả, format_number bắt nhầm tên model chip (M6, A20) do regex thiếu tech units; (2) Cấm tuyệt đối tự sinh giá trị: bar_compare chỉ vẽ 2 cột khi có >=2 số thật từ evidence; 1 số tự chuyển sang stat_number/gauge_needle/slot_counter; thẻ số không parse được chuyển text_focus định tính; (3) Nâng cấp format_number: hỗ trợ đầy đủ tech units (nm, Hz, TB, nit, W, mAh...), parse chuẩn '2nm' -> '2 nm', '120Hz' -> '120 Hz', '54,99 triệu đồng', loại trừ model name; count_up đi 1 mạch từ 0 đến đúng target value, không bao giờ nhảy ngược về 0; (4) Validator sau planner và sau render: numeric_hallucinations bắt trúng và tự loại bỏ số bịa, kiểm tra chặt chẽ % chỉ được xuất hiện khi narration/brief có %; repair_numeric_cards tự động co số thô >6 chữ số thành quy mô rút gọn (triệu, tỷ); kiểm thử hồi quy 6 project (iphone-18e, artemis, co-hoi-ty-usd, giai-thuong, chatbot, macbook-pro-oled) đạt 0 vi phạm; (5) Dòng nguồn rút gọn: tối đa 2 nguồn, 1 dòng, font >=36px, vùng y in [1245, 1280], không đè phụ đề; (6) Giải quyết triệt để cảnh báo đỏ layout Scene 3 macbook-pro-oled (bbox_overlaps = 0 với recipe slot_counter); (7) Bật MOTION_RECIPES_ENABLED=true trong .env/.env.example, tích hợp 28 recipes vào pipeline thật; dựng lại macbook-pro-oled (auto-cong-nghe-d56d3ebe) đạt overall_all_passed: True (100% 6 cảnh đạt chuẩn); (8) Pytest 40/40 tests passed 100%. | APP/editor/motion/engine/recipes.js, editor/motion/recipes/vocabulary.js, editor/format_number.py, agents/visual_diversity.py, agents/illustrations.py, tools/audit_video.py, .env.example, .env; ROOT/docs/PROCESS.md | Hoàn thành Ưu tiên tuyệt đối - Chống bịa số, làm sạch nguồn, giải quyết bbox overlap và nối recipe vào pipeline thật |'''

# Insert vào Mục 2
marker2 = '| 2026-10-28 | Giai đoạn 7 - Bước (d):'
assert marker2 in text, 'marker2 not found'
text = text.replace(marker2, f'{entry_sec2}\n{marker2}', 1)

# Insert vào Mục 15
marker15 = '| 2026-10-28 | Giai đoạn 7 - Nối Recipe vào Pipeline thật:'
assert marker15 in text, 'marker15 not found'
text = text.replace(marker15, f'{entry_sec2}\n{marker15}', 1)

with open('docs/PROCESS.md', 'w', encoding='utf-8') as f:
    f.write(text)
print('Successfully updated PROCESS.md changelog in section 2 and section 15')
