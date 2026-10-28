"""Unit tests for editor/format_number.py."""
import pytest
from editor.format_number import (
    parse_display_number,
    format_vi_number,
    format_count_up,
    NumberKind
)


def test_parse_display_number_core_cases():
    """Verify standard test cases required by project policy."""
    # 1. "65 tỷ USD"
    p1 = parse_display_number("65 tỷ USD")
    assert p1 is not None
    assert p1.value == 65.0
    assert p1.scale == "tỷ"
    assert p1.currency == "USD"
    assert p1.kind == NumberKind.MONEY
    assert p1.formatted_text == "65 tỷ USD"
    assert p1.formatted_number == "65"
    assert p1.full_numeric_value == 65_000_000_000.0

    # 2. "29,25 tỷ"
    p2 = parse_display_number("29,25 tỷ")
    assert p2 is not None
    assert p2.value == 29.25
    assert p2.scale == "tỷ"
    assert p2.kind == NumberKind.MONEY
    assert p2.formatted_text == "29,25 tỷ"
    assert p2.formatted_number == "29,25"
    assert p2.full_numeric_value == 29_250_000_000.0

    # 3. "10 tỷ USD"
    p3 = parse_display_number("10 tỷ USD")
    assert p3 is not None
    assert p3.value == 10.0
    assert p3.scale == "tỷ"
    assert p3.currency == "USD"
    assert p3.kind == NumberKind.MONEY
    assert p3.formatted_text == "10 tỷ USD"
    assert p3.formatted_number == "10"
    assert p3.full_numeric_value == 10_000_000_000.0

    # 4. "36,2%"
    p4 = parse_display_number("36,2%")
    assert p4 is not None
    assert p4.value == 36.2
    assert p4.kind == NumberKind.PERCENT
    assert p4.scale == ""
    assert p4.currency == ""
    assert p4.formatted_text == "36,2%"
    assert p4.formatted_number == "36,2"

    # 5. "5,95%"
    p5 = parse_display_number("5,95%")
    assert p5 is not None
    assert p5.value == 5.95
    assert p5.kind == NumberKind.PERCENT
    assert p5.formatted_text == "5,95%"
    assert p5.formatted_number == "5,95"

    # 6. "60 USD"
    p6 = parse_display_number("60 USD")
    assert p6 is not None
    assert p6.value == 60.0
    assert p6.kind == NumberKind.MONEY
    assert p6.currency == "USD"
    assert p6.scale == ""
    assert p6.formatted_text == "60 USD"
    assert p6.formatted_number == "60"


def test_format_vi_number():
    """Verify Vietnamese number decimal comma and thousand dot."""
    assert format_vi_number(65) == "65"
    assert format_vi_number(29.25) == "29,25"
    assert format_vi_number(1000) == "1.000"
    assert format_vi_number(1250000) == "1.250.000"
    assert format_vi_number(5.95) == "5,95"


def test_count_up_on_reduced_value():
    """Verify count_up animates on reduced scale (0 -> 65 tỷ USD, never 65000000000)."""
    p = parse_display_number("65 tỷ USD")
    
    # At start (0%)
    res_start = format_count_up(p, 0.0)
    assert "tỷ USD" in res_start
    assert "65.000.000.000" not in res_start
    
    # At finish (100%)
    res_end = format_count_up(p, 1.0)
    assert res_end == "65 tỷ USD"
