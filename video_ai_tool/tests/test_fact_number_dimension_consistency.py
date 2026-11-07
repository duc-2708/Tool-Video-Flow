"""Regression tests for FactNumber dimension consistency, unit validation, and entity disambiguation.

Enforces:
1. 'máy đào hầm đường kính 6,5 m, hầm dài 4 km' -> TBM = 6,5 m, tuyến = 4 km (never 3 km or 4 km for diameter).
2. UNIT_QUANTITY_TABLE:
   - DIMENSION (đường kính, chiều cao, độ sâu, độ dày) -> m, cm, mm (cấm km).
   - DISTANCE (chiều dài tuyến, quãng đường) -> km, m.
   - CURRENCY -> tỷ/triệu đồng/USD.
   - SPEED -> km/h, m/s.
   - RATIO -> %.
3. Rejection of invalid unit-quantity combinations (e.g. diameter in km).
4. Disambiguation of ordinal numbers ('tuyến số 3', 'máy số 1', 'ga số 4').
"""
from __future__ import annotations

import pytest

from schemas.fact_number import (
    validate_unit_quantity,
    extract_facts_from_text,
    UNIT_QUANTITY_TABLE,
)


def test_tbm_diameter_vs_tunnel_length_disambiguation():
    """Requirement 1d: 'máy đào hầm đường kính 6,5 m, hầm dài 4 km'
    Must parse TBM diameter as 6,5 m and tunnel length as 4 km without confusing or swapping units.
    """
    sentence = "Dự án sử dụng máy đào hầm đường kính 6,5 m, hầm dài 4 km dưới lòng thành phố."
    facts = extract_facts_from_text(sentence)

    # Must extract 2 distinct facts
    assert len(facts) >= 2

    # Fact 1: TBM diameter = 6.5 m
    tbm_fact = next((f for f in facts if "đường kính" in f.label.lower() or "tbm" in f.label.lower()), None)
    assert tbm_fact is not None
    assert str(tbm_fact.value) in ("6.5", "6,5")
    assert str(tbm_fact.unit).lower() in ("m", "mét")
    assert tbm_fact.unit.lower() != "km"
    assert tbm_fact.start_offset >= 0
    assert tbm_fact.end_offset > tbm_fact.start_offset

    # Fact 2: Tunnel length = 4 km
    tunnel_fact = next((f for f in facts if "dài" in f.label.lower() or "hầm" in f.label.lower() or "tuyến" in f.label.lower()), None)
    assert tunnel_fact is not None
    assert str(tunnel_fact.value) in ("4", "4.0")
    assert str(tunnel_fact.unit).lower() == "km"


@pytest.mark.parametrize(
    ("sentence", "expected_label_kw", "expected_val", "expected_unit"),
    [
        # Case 1: Chiều sâu đào ngầm
        (
            "Nhà ga ngầm được đào ở độ sâu 29 m dưới mặt đất.",
            "sâu",
            "29",
            "m",
        ),
        # Case 2: Độ dày tường vây
        (
            "Công trình gia cố bằng tường vây bê tông có độ dày 1,2 m.",
            "dày",
            "1.2",
            "m",
        ),
        # Case 3: Chiều cao thông thủy
        (
            "Đoạn hầm kỹ thuật đạt chiều cao 4,5 m đáp ứng tiêu chuẩn.",
            "cao",
            "4.5",
            "m",
        ),
        # Case 4: Chiều dài toàn tuyến
        (
            "Toàn tuyến đường sắt đô thị có chiều dài 12,5 km qua các quận trung tâm.",
            "dài",
            "12.5",
            "km",
        ),
        # Case 5: Tổng mức đầu tư (Tiền tệ)
        (
            "Dự án có tổng mức đầu tư khoảng 34.000 tỷ đồng từ nguồn vốn công.",
            "đầu tư",
            "34000",
            "tỷ đồng",
        ),
        # Case 6: Tốc độ tối đa
        (
            "Đoàn tàu điện vận hành với vận tốc tối đa 80 km/h.",
            "tốc",
            "80",
            "km/h",
        ),
        # Case 7: Tỷ lệ tiến độ
        (
            "Gói thầu ngầm hiện đã hoàn thành 85% khối lượng thi công.",
            "hoàn thành",
            "85",
            "%",
        ),
    ],
)
def test_six_sample_sentences_grounded_extraction(
    sentence: str,
    expected_label_kw: str,
    expected_val: str,
    expected_unit: str,
):
    """Test at least 6 diverse domain sentences for dimensions, currency, speed, and ratios."""
    facts = extract_facts_from_text(sentence)
    assert len(facts) >= 1

    matched = next((f for f in facts if expected_label_kw in f.label.lower()), None)
    assert matched is not None, f"Could not find fact with label '{expected_label_kw}' in {[f.label for f in facts]}"
    assert str(matched.value).replace(",", ".") == expected_val.replace(",", ".")
    assert matched.unit.lower().replace(" ", "") == expected_unit.lower().replace(" ", "")
    assert matched.source_sentence == sentence
    assert matched.start_offset >= 0
    assert matched.end_offset > matched.start_offset


def test_unit_quantity_table_rejection():
    """Unit vs quantity table must strictly reject absurd units (e.g. km for diameter)."""
    # Diameter cannot be km
    valid, err = validate_unit_quantity("Đường kính máy đào hầm TBM", "km", 3)
    assert not valid
    assert "DIMENSION" in err

    # Height cannot be km
    valid, err = validate_unit_quantity("Chiều cao tầng hầm", "km", 5)
    assert not valid
    assert "DIMENSION" in err

    # Thickness cannot be km
    valid, err = validate_unit_quantity("Độ dày tường vây", "km", 1)
    assert not valid
    assert "DIMENSION" in err

    # Depth cannot be km
    valid, err = validate_unit_quantity("Độ sâu hố đào", "km", 2)
    assert not valid
    assert "DIMENSION" in err

    # Speed cannot be tỷ đồng
    valid, err = validate_unit_quantity("Tốc độ chạy tàu", "tỷ đồng", 100)
    assert not valid
    assert "SPEED" in err

    # Ratio cannot be km
    valid, err = validate_unit_quantity("Tỷ lệ tăng trưởng", "km", 15)
    assert not valid
    assert "RATIO" in err


def test_ordinal_number_filtering():
    """Ordinal numbers like 'tuyến số 3', 'máy số 1', 'ga số 4' must not become facts."""
    sentence = "Tuyến metro số 3 huy động máy đào số 1 để thi công ga số 4."
    facts = extract_facts_from_text(sentence)
    # None of the ordinal numbers (3, 1, 4) should be extracted as statistical measurement facts
    assert len(facts) == 0


def test_metaphor_detection_and_sanitization():
    """Ensure metaphors (đồ chơi, lắp ráp trong hộp kín, bánh kem, ống hút, tựa như...) are caught and sanitized."""
    from editor.motion.light_glass_slots import contains_metaphor, _sanitize_metaphor

    metaphors = [
        "Việc lắp ráp đồ chơi trong hộp kín",
        "Mũi khoan như chiếc ống hút cắm vào bánh kem",
        "Tựa như một bức tranh",
        "Chẳng khác gì cỗ máy thời gian",
        "Được ví như bác sĩ nội soi",
    ]
    for m in metaphors:
        assert contains_metaphor(m), f"Should detect metaphor in: '{m}'"
        sanitized = _sanitize_metaphor(m)
        assert not contains_metaphor(sanitized), f"Sanitized text still has metaphor: '{sanitized}'"


def test_title_subtitle_overlap_check():
    """Ensure title-subtitle overlap >= 60% is detected."""
    from editor.motion.light_glass_slots import check_title_subtitle_overlap

    # High overlap (>= 60%)
    title = "Kỹ sư Việt Nam làm chủ công nghệ đào hầm"
    sub = "Kỹ sư Việt Nam làm chủ công nghệ đào hầm đô thị"
    overlap = check_title_subtitle_overlap(title, sub)
    assert overlap >= 0.60

    # Low overlap (< 60%)
    sub2 = "Đoạn tuyến 4 km xuyên qua bốn ga ngầm trọng điểm"
    overlap2 = check_title_subtitle_overlap(title, sub2)
    assert overlap2 < 0.60


def test_kit_route_extraction_and_planning():
    """Ensure >= 3 sequential stations produce kit_route layout."""
    from editor.motion.light_glass_slots import _extract_route_stations, create_heuristic_slide_script

    corpus = "Tuyến metro ngầm 4 km đi qua Ga Kim Mã, Ga Cát Linh, Ga Văn Miếu và Ga Hà Nội."
    route_data = _extract_route_stations(corpus)
    assert route_data is not None
    assert len(route_data["stations"]) >= 3
    assert "Ga Kim Mã" in route_data["stations"]
    assert "Ga Cát Linh" in route_data["stations"]
    assert "Ga Văn Miếu" in route_data["stations"]
    assert "Ga Hà Nội" in route_data["stations"]
    assert "4 km" in route_data["distance"]

    # In heuristic slide planner: must contain at least one kit_route slide
    sentences = [
        {"id": 1, "text": "Kỹ sư Việt Nam làm chủ công nghệ khoan ngầm hiện đại.", "duration": 5.0, "start": 0.0, "end": 5.0},
        {"id": 2, "text": "Tuyến ngầm 4 km kết nối các ga ngầm Kim Mã, Cát Linh, Văn Miếu và Ga Hà Nội.", "duration": 5.2, "start": 5.0, "end": 10.2},
        {"id": 3, "text": "Máy đào hầm TBM có đường kính 6,5 m vận hành chuẩn xác.", "duration": 4.8, "start": 10.2, "end": 15.0},
        {"id": 4, "text": "Công trình đặt dấu mốc quan trọng cho hạ tầng giao thông đô thị.", "duration": 5.0, "start": 15.0, "end": 20.0},
        {"id": 5, "text": "Việt Nam tự chủ hoàn toàn kỹ thuật thi công ngầm phức tạp.", "duration": 5.0, "start": 20.0, "end": 25.0},
    ]
    script = create_heuristic_slide_script(sentences, total_duration=25.0)
    layouts = [s.layout for s in script.slides]
    assert "kit_route" in layouts
    route_slide = next(s for s in script.slides if s.layout == "kit_route")
    assert len(route_slide.slots.get("stations", [])) >= 3

    # All slide durations must be strictly between 3.5s and 6.5s
    for s in script.slides:
        assert 3.5 <= s.duration <= 6.5, f"Slide {s.id} duration {s.duration} outside [3.5, 6.5]s"

