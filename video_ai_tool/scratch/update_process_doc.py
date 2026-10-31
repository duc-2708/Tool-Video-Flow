from pathlib import Path

process_file = Path("docs/PROCESS.md")
if not process_file.exists():
    process_file = Path("../docs/PROCESS.md")

code = process_file.read_text(encoding="utf-8")

old_header = "| Ngày | Thay đổi | File | Lý do |\n|---|---|---|---|\n"
if old_header not in code:
    old_header = "| Ngày | Thay đổi | File | Lý do |\r\n|---|---|---|---|\r\n"

new_entry = (
    "| 2026-10-31 | Khắc phục triệt để 5 nhóm lỗi cho video \"bao-lo-hong-va-nguy-co-an-ninh-mang-thang-10\" (output/auto-cong-nghe-e97dccbd): "
    "(1) Khung ma & thẻ trống: xóa bỏ hoàn toàn 2 vòng tròn mờ rỗng trong renderTextFocus (recipes.js), thay bằng biểu tượng vector khiên; "
    "co giãn nhịp thời gian items thích ứng độ dài shot trong renderChecklist, renderStackCards, renderMockUIWindow đảm bảo hiển thị đủ nội dung trong shot 2.5-2.8s; "
    "đo ink element count (>=3) và ink area ratio (>=25% hero frame) tại >=3 mốc, cấm thẻ trống; "
    "(2) Số liệu: loại bỏ đệm 0 trong renderSlotCounter và renderOdometer (hiển thị \"84\" không đệm \"0084\"); gauge_needle dừng chuẩn 84% không non 76.8%; "
    "scheduler loại trừ ngày/tháng/năm (\"Tháng 10\", \"năm 2026\") khỏi has_number; cấm dùng recipe số khi shot không có số trong lời đọc (chỉ duy nhất shot 16 có 84%); "
    "(3) Lặp recipe: schedule_shots_no_repeat ràng buộc cứng max_freq <= 2 và min_dist >= 4; 20 shots phân bổ 12 recipes đa dạng, khoảng cách cùng recipe đều >= 5 shots; "
    "(4) Nhãn tối nghĩa: bỏ cắt cụt 4 từ, nâng trần 6 từ và bảo toàn các từ ghép (\"Khóa cửa lỗi thiết kế\", \"Hàng triệu nỗ lực khai thác\", \"Lỗ hổng PHP nghiêm trọng\", \"Vá máy chủ toàn cầu\", \"Lộ thông tin đăng nhập\", \"Tự động quét điểm yếu\"); orbit_system có đủ center_node và satellites từ câu nói; "
    "(5) Diện tích Hero: nâng cardW = 880 (>=880px) và cardH >= 680 (>=55% vùng an toàn y in [240, 1330]) trên toàn bộ recipes. "
    "Render MP4 55.27s (1080x1920), 15/15 chỉ số layout audit PASSED, xuất contact sheet 23 khung hình, pytest 26/26 passed, ruff F821 all passed. | "
    "APP/editor/motion/recipes/vocabulary.js, editor/motion/engine/recipes.js, editor/motion/scheduler.py, editor/motion/runtime.js, pipeline/render_motion.py, agents/presentation.py, tools/rerun_bao_lo_hong.py, tests/test_fix_ghost_cards_numbers_repetition.py; ROOT/docs/PROCESS.md | "
    "Hoàn thành toàn diện yêu cầu sửa lỗi khung ma, chuẩn hóa số liệu không đệm 0, đa dạng hóa recipe và bảo đảm kích thước hero frame an toàn |\n"
)

code = code.replace(old_header, old_header + new_entry, 1)

# Also update checklist item for recent regression run in section 13.4
evidence_marker = "### 13.4 Bằng chứng hồi quy local đang có\n"
if evidence_marker not in code:
    evidence_marker = "### 13.4 Bằng chứng hồi quy local đang có\r\n"

new_evidence = (
    "- Bão Lỗ Hổng Và Nguy Cơ An Ninh Mạng Tháng 10 (`output/auto-cong-nghe-e97dccbd`): "
    "5 cảnh, 20 shots, thời lượng MP4 final 55.272s (1080x1920, 30fps). "
    "Sử dụng 12 recipes đa dạng (orbit_system, puzzle_snap, shield_hit, stack_pile, layered_onion, tug_of_war, lock_unlock, vs_flip_cards, camera_surveillance_scan, slot_counter, conveyor_belt, domino_chain); "
    "mỗi recipe tối đa 2 lần, không lặp trong 5 shots liền kề; 100% nhãn bám sát câu (không bị cắt cụt từ ghép); "
    "số liệu duy nhất 84% tại shot 16 hiển thị chính xác không đệm 0; "
    "15/15 chỉ số layout audit PASSED (hero_width 940px, hero_area 100%, 0 clipped rows, 0 caption collisions); "
    "contact sheet 23 khung hình tại `review_frames/contact_sheet.png`.\n"
)

code = code.replace(evidence_marker, evidence_marker + new_evidence, 1)

process_file.write_text(code, encoding="utf-8")
print("PROCESS.md updated successfully!")
