import pytest
from agents.presentation import clean_semantic_label, TRAILING_CUTOFF, LEADING_CUTOFF

def test_clean_semantic_label_dangling_cutoffs():
    assert clean_semantic_label("Sự đồng thuận này giống") == "Sự đồng thuận"
    assert clean_semantic_label("Minh họa ý") == ""
    assert clean_semantic_label("Minh họa ý tưởng") == ""
    assert clean_semantic_label("Tác động công nghệ của") == "Tác động công nghệ"
    assert clean_semantic_label("Kinh tế tầm thấp tại") == "Kinh tế tầm thấp"
    assert clean_semantic_label("Vấn đề kiểm soát thì") == "Vấn đề kiểm soát"

def test_clean_semantic_label_length_limit():
    # Long label trimmed to <= 4 words
    raw = "Hệ thống đường bay số hóa trên toàn quốc"
    cleaned = clean_semantic_label(raw)
    words = cleaned.split()
    assert 2 <= len(words) <= 4
    assert words[-1].lower() not in TRAILING_CUTOFF
