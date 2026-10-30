"""Test kiểm tra lập lịch ngữ nghĩa, liên kết nội dung lời đọc và cảnh recap cuối."""
from editor.motion.scheduler import (
    extract_shot_brief_and_data,
    enough_for_shot,
    schedule_shots_no_repeat,
    NUMERIC_RECIPES
)


def test_extract_shot_brief_and_data_semantic_intents():
    """Trích xuất ý chính câu và phân loại đúng intent từ lời đọc."""
    # 1. Câu có số liệu
    b1 = extract_shot_brief_and_data("Ashley Griffith đối mặt với 202 tội danh lạm dụng.")
    assert b1["has_number"] is True
    assert b1["value"] == 202.0
    assert b1["intent"] == "number"

    # 2. Câu so sánh
    b2 = extract_shot_brief_and_data("Đánh giá cho biết cơ hội phát hiện so với thực tế bị bỏ lỡ.")
    assert b2["intent"] == "compare"

    # 3. Câu rủi ro, bảo mật, giam giữ
    b3 = extract_shot_brief_and_data("Hàng rào bảo vệ có nhiều khoảng trống và bị tấn công.")
    assert b3["intent"] == "risk"

    # 4. Câu recap cuối
    b4 = extract_shot_brief_and_data("Vì sao những dấu hiệu cảnh báo lại bị bỏ quên?", is_recap=True)
    assert b4["intent"] == "recap"


def test_enough_for_shot_strict_validation():
    """enough_for_shot kiểm tra nghiêm ngặt dữ liệu của recipe, cấm chọn thẻ trống hoặc số ảo."""
    # Recipe số thiếu số -> False
    assert enough_for_shot("slot_counter", {"has_number": False, "value": None}) is False
    assert enough_for_shot("odometer", {"has_number": False, "value": None}) is False
    assert enough_for_shot("gauge_needle", {"has_number": False, "value": None}) is False

    # Recipe số có số thật -> True
    assert enough_for_shot("slot_counter", {"has_number": True, "value": 202.0}) is True
    assert enough_for_shot("odometer", {"has_number": True, "value": 1000.0}) is True

    # Cấm layered_onion / stack_pile làm thẻ trống không có nhãn
    assert enough_for_shot("layered_onion", {"label": ""}) is False
    assert enough_for_shot("layered_onion", {"label": "chi tiết"}) is False
    assert enough_for_shot("layered_onion", {"label": "Lớp khóa bí mật"}) is True


def test_schedule_shots_no_repeat_diversity_and_recap():
    """Lập lịch >= 8 recipe khác nhau, không lặp 2 shot liền kề, recap có checklist >= 3 events."""
    shots = [
        {"duration_sec": 3.0, "narration": "Hơn hai trăm lẻ hai tội danh mới vừa được công bố."},
        {"duration_sec": 3.0, "narration": "Ashley Paul Griffith hiện đang bị giam giữ nghiêm ngặt."},
        {"duration_sec": 3.0, "narration": "Cơ hội bỏ lỡ tới 5 lần nếu có hệ thống báo cáo."},
        {"duration_sec": 3.0, "narration": "So sánh giữa hệ thống cũ và quy trình kiểm soát mới."},
        {"duration_sec": 3.0, "narration": "Hàng rào bảo vệ an ninh xuất hiện nhiều lỗ hổng."},
        {"duration_sec": 3.0, "narration": "Băng chuyền xử lý dữ liệu và hình ảnh thu giữ."},
        {"duration_sec": 3.0, "narration": "Đèn tín hiệu cảnh báo nguy cơ vi phạm tiếp diễn."},
        {"duration_sec": 3.0, "narration": "Mạng lưới đường ống liên thông giữa các cơ quan."},
        {"duration_sec": 3.0, "narration": "Quy trình điều tra thu thập hàng nghìn chứng cứ."},
        {"duration_sec": 4.0, "narration": "Tổng kết vụ việc và trình tự pháp lý sang tháng sau.", "is_recap": True},
    ]

    scheduled, notes = schedule_shots_no_repeat(shots, min_distinct=8, min_dist=2, max_freq=2)

    # 1. Ít nhất 8 recipes khác nhau
    distinct_recipes = {s["recipe"] for s in scheduled}
    assert len(distinct_recipes) >= 8, f"Yêu cầu >= 8 recipes khác nhau, nhận được {len(distinct_recipes)}: {distinct_recipes}"

    # 2. Không 2 shot liền kề trùng recipe
    for i in range(1, len(scheduled)):
        assert scheduled[i]["recipe"] != scheduled[i-1]["recipe"], f"Shot {i} và {i+1} trùng recipe: {scheduled[i]['recipe']}"

    # 3. Mỗi recipe tối đa 2 lần
    from collections import Counter
    counts = Counter(s["recipe"] for s in scheduled)
    for r, c in counts.items():
        assert c <= 2, f"Recipe {r} xuất hiện {c} lần (>2)"

    # 4. Shot recap cuối cùng sử dụng checklist/orbit_system với >= 3 sự kiện
    last_shot = scheduled[-1]
    assert last_shot["recipe"] in {"checklist", "orbit_system", "lock_unlock"}
    assert len(last_shot["beats"]) >= 3
