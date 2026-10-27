"""Tests for Motion Design System and Layout Auditor (Phase 4b)."""
import pytest
from pathlib import Path
from agents.presentation import clean_semantic_label, labels_are_duplicate, valid_card
from utils.caption_timing import phrase_groups
from tools.audit_video import audit_project, METRICS_SPEC


def test_clean_semantic_label_eliminates_cutoffs():
    assert clean_semantic_label("Sự cố đột") == "Sự cố"
    assert clean_semantic_label("Cố đột ngột") == "Đột ngột"
    assert clean_semantic_label("Việc tôn vinh") == "Tôn vinh"
    assert clean_semantic_label("Tôn vinh cá") == "Tôn vinh"
    assert clean_semantic_label("Hành động đóng") == "Hành động"
    assert clean_semantic_label("Điều giống dàn") == ""
    assert clean_semantic_label("Giống dàn nhạc") == "Dàn nhạc"


def test_labels_are_duplicate():
    assert labels_are_duplicate("Sự cố", "Sự cố đột ngột")
    assert labels_are_duplicate("Việc tôn vinh", "Tôn vinh cá nhân")
    assert labels_are_duplicate("Hành động", "Hành động đóng vai")
    assert not labels_are_duplicate("Thợ cắt tóc", "Thủ tướng")


def test_valid_card_rejects_cutoffs():
    assert not valid_card("Sự cố đột")
    assert not valid_card("Cố đột ngột")
    assert not valid_card("Hành động đóng")
    assert valid_card("Sự cố đột ngột")
    assert valid_card("Cá nhân dũng cảm")


def test_phrase_groups_min_duration():
    words = [
        ("Dân", 0.0, 0.2),
        ("biểu", 0.2, 0.4),
        ("Helen", 0.4, 0.8),
        ("Haines", 0.8, 1.2),
        ("bị", 1.2, 1.4),
        ("xe", 1.4, 1.6),
        ("tông", 1.6, 2.0)
    ]
    groups = phrase_groups(words, count=3, min_group_duration=0.7)
    for g in groups:
        assert len(g) <= 4
        dur = g[-1][2] - g[0][1]
        assert dur >= 0.7 or len(groups) == 1


def test_audit_project_on_fixture():
    project_dir = Path("output/auto-tin-tuc-d4eaf7a9")
    if project_dir.exists():
        report = audit_project(project_dir)
        assert report["overall_all_passed"]
        for s in report["scenes"]:
            m = s["metrics"]
            assert m["hero_width"] >= 880
            assert m["hero_area_ratio"] >= 0.45
            assert m["min_font_size"] >= 36
            assert m["clipped_rows"] == 0
            assert m["bbox_overlaps"] == 0
            assert m["t0_visible_count"] <= 1
            assert m["max_still_interval_sec"] <= 1.2
            assert m["empty_space_ratio"] <= 0.35
            assert m["duplicate_labels"] == 0
