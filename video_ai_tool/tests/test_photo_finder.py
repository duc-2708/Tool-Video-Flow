"""Unit tests for PhotoFinder, FactNumber Grounding, Real Charts, and Metaphor/Subsequence Filters.

Uses 100% mocked HTTP (zero remote API calls, no network cost, safe offline verification).
"""
import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from agents.photo_finder import (
    PhotoFinder,
    clean_artist_name,
    is_license_allowed,
    rank_wikimedia_candidates,
    search_wikidata_person,
    verify_wikidata_is_human,
)
from editor.motion.light_glass_slots import (
    contains_metaphor,
    is_valid_subsequence_of_narration,
    _sanitize_metaphor,
    FORBIDDEN_BOILERPLATE_LABELS,
)
from schemas.fact_number import (
    FactNumber,
    extract_facts_from_text,
    extract_facts_from_brief,
    parse_vietnamese_number,
    select_chart_for_facts,
)


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    p = tmp_path / "test_project"
    p.mkdir(parents=True, exist_ok=True)
    return p


def create_dummy_image_bytes(w: int = 1920, h: int = 1080) -> bytes:
    im = Image.new("RGB", (w, h), color=(80, 120, 160))
    buf = io.BytesIO()
    im.save(buf, format="JPEG")
    return buf.getvalue()


# -------------------------------------------------------------
# 1. License Safety Checks
# -------------------------------------------------------------
def test_allowed_licenses():
    assert is_license_allowed("CC0")
    assert is_license_allowed("CC BY 4.0")
    assert is_license_allowed("CC-BY-SA 3.0")
    assert is_license_allowed("Public Domain")
    assert is_license_allowed("pd-self")
    assert is_license_allowed("CC BY-SA")


def test_forbidden_licenses():
    assert not is_license_allowed("CC BY-NC 4.0")
    assert not is_license_allowed("CC BY-NC-SA 3.0")
    assert not is_license_allowed("CC BY-ND 4.0")
    assert not is_license_allowed("All Rights Reserved")
    assert not is_license_allowed("Copyrighted free use")
    assert not is_license_allowed("fair use")
    assert not is_license_allowed("")
    assert not is_license_allowed(None)


def test_clean_artist_name():
    assert clean_artist_name('<a href="https://example.com">John Doe</a>') == "John Doe"
    assert clean_artist_name('<bdi>Gage Skidmore</bdi>') == "Gage Skidmore"
    assert clean_artist_name("User:WikimediaContributor") == "Wikimedia Commons"
    assert clean_artist_name("") == "Wikimedia Commons"


# -------------------------------------------------------------
# 2. Wikidata Verification & Person Matching
# -------------------------------------------------------------
@patch("requests.get")
def test_verify_wikidata_is_human(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "entities": {
            "Q317521": {
                "claims": {
                    "P31": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}
                    ]
                }
            }
        }
    }
    mock_get.return_value = mock_resp
    assert verify_wikidata_is_human("Q317521") is True


@patch("requests.get")
def test_verify_wikidata_not_human(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "entities": {
            "Q12345": {
                "claims": {
                    "P31": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q4830453"}}}}  # Business
                    ]
                }
            }
        }
    }
    mock_get.return_value = mock_resp
    assert verify_wikidata_is_human("Q12345") is False


# -------------------------------------------------------------
# 3. Person in Narration vs Person NOT in Narration
# -------------------------------------------------------------
@patch("agents.photo_finder.detect_faces", return_value=(1, []))
@patch("agents.photo_finder.detect_text_slide_document", return_value=(False, 0, "ok"))
@patch("agents.photo_finder.is_document_or_schematic_image", return_value=(False, "ok"))
@patch("requests.get")
def test_person_named_in_narration_accepted(mock_get, mock_doc, mock_text, mock_faces, temp_project):
    # Mock Wikidata search -> Q317521
    def side_effect(url, params=None, headers=None, timeout=None):
        resp = MagicMock()
        resp.status_code = 200
        if "wbsearchentities" in str(params):
            resp.json.return_value = {"search": [{"id": "Q317521"}]}
        elif "wbgetclaims" in str(params):
            prop = (params or {}).get("property")
            if prop == "P31":
                resp.json.return_value = {"claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}]}}
            elif prop == "P18":
                resp.json.return_value = {"claims": {"P18": [{"mainsnak": {"datavalue": {"value": "Elon_Musk_2023.jpg"}}}]}}
            else:
                resp.json.return_value = {"claims": {}}
        elif "wbgetentities" in str(params):
            resp.json.return_value = {
                "entities": {
                    "Q317521": {
                        "claims": {
                            "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}],
                            "P18": [{"mainsnak": {"datavalue": {"value": "Elon_Musk_2023.jpg"}}}],
                        }
                    }
                }
            }
        elif "commons.wikimedia.org" in url and "imageinfo" in str(params):
            resp.json.return_value = {
                "query": {
                    "pages": {
                        "123": {
                            "title": "File:Elon_Musk_2023.jpg",
                            "imageinfo": [{
                                "url": "https://upload.wikimedia.org/elon.jpg",
                                "width": 2000,
                                "height": 2000,
                                "extmetadata": {
                                    "Artist": {"value": "Gage Skidmore"},
                                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                }
                            }]
                        }
                    }
                }
            }
        elif "upload.wikimedia.org" in url:
            resp.content = create_dummy_image_bytes(2000, 2000)
        return resp

    mock_get.side_effect = side_effect
    finder = PhotoFinder(temp_project)

    # Elon Musk is mentioned verbatim in narration
    res = finder.find_photo_for_scene(
        slide_id="slide_1",
        narration="Elon Musk phát biểu về tương lai của trí tuệ nhân tạo.",
        brief={"facts": []},
        headline="Elon Musk Cảnh Báo",
    )
    assert res is not None
    assert res["name"] == "Elon Musk"
    assert res["type"] == "person"
    assert "CC BY-SA 4.0" in res["caption"]
    assert "Gage Skidmore" in res["caption"]
    assert Path(res["image_path"]).is_file()

    # Check persistence in photo_attributions.json & credits.txt
    attr_file = temp_project / "photo_attributions.json"
    assert attr_file.is_file()
    attrs = json.loads(attr_file.read_text(encoding="utf-8"))
    assert len(attrs) == 1
    assert attrs[0]["entity"] == "Elon Musk"

    credits_file = temp_project / "credits.txt"
    assert credits_file.is_file()
    assert "Elon Musk" in credits_file.read_text(encoding="utf-8")


@patch("agents.photo_finder.search_wikimedia_commons", return_value=[])
def test_person_not_named_in_narration_rejected(mock_search, temp_project):
    finder = PhotoFinder(temp_project)
    # Donald Trump or Elon Musk is NOT in narration
    res = finder.find_photo_for_scene(
        slide_id="slide_2",
        narration="Công nghệ thi công hầm ngầm đang được triển khai tại Hà Nội.",
        brief={"facts": []},
        headline="Thi Công Đường Hầm",
    )
    # Must NOT attach a person
    if res:
        assert res["type"] != "person"


# -------------------------------------------------------------
# 4. Landmark / Machine Ranking
# -------------------------------------------------------------
def test_rank_wikimedia_candidates():
    candidates = [
        {"title": "File:Random Flower Garden.jpg", "categories": "Nature, Flowers", "url": "http://a.jpg"},
        {"title": "File:Tunnel Boring Machine in Singapore.jpg", "categories": "Singapore MRT, TBM tunnels", "url": "http://b.jpg"},
        {"title": "File:Subway Tunnel Metro Line 1.jpg", "categories": "Subway tunnels", "url": "http://c.jpg"},
    ]
    scene_entities = ["tbm", "tunnel boring machine", "singapore", "đường hầm"]
    ranked = rank_wikimedia_candidates(candidates, scene_entities)

    assert len(ranked) == 2
    # The Singapore TBM candidate matches multiple entities in title and categories
    assert ranked[0]["title"] == "File:Tunnel Boring Machine in Singapore.jpg"
    assert "tunnel boring machine" in [e.lower() for e in ranked[0]["matched_entities"]]


# -------------------------------------------------------------
# 5. FactNumber Extraction & Real Charts
# -------------------------------------------------------------
def test_vietnamese_number_parsing():
    assert parse_vietnamese_number("1.541") == 1541
    assert parse_vietnamese_number("1,541") == 1541
    assert parse_vietnamese_number("35%") == 35
    assert parse_vietnamese_number("410") == 410
    assert parse_vietnamese_number("4,5") == 4.5
    assert parse_vietnamese_number("4.5") == 4.5


def test_extract_facts_from_text():
    text = (
        "Dự án đường sắt tốc độ cao có chiều dài 1.541 km được Quốc hội thông qua. "
        "Trong đó đoạn ưu tiên Hà Nội - Vinh dài 410 km hoàn thành năm 2028. "
        "Chi phí xây dựng ước tính chiếm 35% tổng mức đầu tư."
    )
    facts = extract_facts_from_text(text, source_url="https://vnexpress.net/du-an-duong-sat")
    assert len(facts) >= 3

    units = [f.unit.lower() for f in facts]
    assert "km" in units
    assert "%" in units

    km_facts = [f for f in facts if f.unit.lower() == "km"]
    vals = [f.value for f in km_facts]
    assert 1541 in vals
    assert 410 in vals
    for f in facts:
        assert f.source_sentence != ""


def test_select_chart_for_facts_line():
    facts = [
        FactNumber(label="Doanh thu", value=100, unit="tỷ đồng", period="Năm 2023", source_sentence="Năm 2023 đạt 100 tỷ."),
        FactNumber(label="Doanh thu", value=150, unit="tỷ đồng", period="Năm 2024", source_sentence="Năm 2024 đạt 150 tỷ."),
        FactNumber(label="Doanh thu", value=220, unit="tỷ đồng", period="Năm 2025", source_sentence="Năm 2025 đạt 220 tỷ."),
    ]
    chart = select_chart_for_facts(facts)
    assert chart is not None
    assert chart["layout"] == "kit_chart_line"
    assert len(chart["series"]) == 3


def test_select_chart_for_facts_donut():
    facts = [
        FactNumber(label="Nông nghiệp", value=40, unit="%", period=None, source_sentence="Nông nghiệp 40%."),
        FactNumber(label="Công nghiệp", value=35, unit="%", period=None, source_sentence="Công nghiệp 35%."),
        FactNumber(label="Dịch vụ", value=25, unit="%", period=None, source_sentence="Dịch vụ 25%."),
    ]
    chart = select_chart_for_facts(facts)
    assert chart is not None
    assert chart["layout"] == "kit_chart_donut"
    assert len(chart["series"]) == 3


def test_select_chart_for_facts_bar():
    facts = [
        FactNumber(label="Việt Nam", value=120, unit="km", period=None, source_sentence="Việt Nam đạt 120 km."),
        FactNumber(label="Thái Lan", value=95, unit="km", period=None, source_sentence="Thái Lan đạt 95 km."),
        FactNumber(label="Malaysia", value=80, unit="km", period=None, source_sentence="Malaysia đạt 80 km."),
    ]
    chart = select_chart_for_facts(facts)
    assert chart is not None
    assert chart["layout"] == "kit_chart_bar"
    assert len(chart["series"]) == 3


def test_no_numbers_brief():
    brief = {
        "facts": [
            {"claim": "Công nghệ thi công hầm ngầm phát triển nhanh", "evidence_quote": "Kỹ sư tự chủ công nghệ."}
        ]
    }
    facts = extract_facts_from_brief(brief)
    assert len(facts) == 0
    chart = select_chart_for_facts(facts)
    assert chart is None


# -------------------------------------------------------------
# 6. Metaphor Filtering & Subsequence Ratio
# -------------------------------------------------------------
def test_metaphor_detection_and_sanitization():
    meta1 = "Hệ thống hoạt động giống như một chiếc gương chiếu hậu phản chiếu rủi ro."
    assert contains_metaphor(meta1) is True
    san1 = _sanitize_metaphor(meta1)
    assert "giống như" not in san1
    assert "chiếc gương" not in san1

    meta2 = "Được ví như bác sĩ nội soi trong lòng đất phức tạp."
    assert contains_metaphor(meta2) is True
    san2 = _sanitize_metaphor(meta2)
    assert "bác sĩ nội soi" not in san2
    assert "được ví như" not in san2

    non_meta = "Làm chủ máy đào hầm TBM dưới lòng đô thị."
    assert contains_metaphor(non_meta) is False


def test_forbidden_boilerplate_labels():
    for label in ("ý chính cần nhớ", "tác động công nghệ", "đây là bước đi thiết thực", "làm thế nào", "cách tiếp cận cũ"):
        assert label in FORBIDDEN_BOILERPLATE_LABELS


def test_subsequence_ratio_check():
    narration = "Cách các kỹ sư Việt Nam làm chủ công nghệ thi công dưới lòng đô thị hiện đại."
    # Valid subset in order
    displayed_good = "Kỹ sư Việt Nam làm chủ công nghệ"
    assert is_valid_subsequence_of_narration(displayed_good, narration, min_ratio=0.80) is True

    # Out of order or fabricated words
    displayed_bad = "Doanh nhân nước ngoài đầu tư bất động sản đô thị"
    assert is_valid_subsequence_of_narration(displayed_bad, narration, min_ratio=0.80) is False
