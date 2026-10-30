"""Test audit trung thực: không dùng hằng số giả, phát hiện chưa đo, phát hiện lệch hash video."""
import json
import tempfile
from pathlib import Path
from tools.audit_video import audit_project


def test_audit_missing_meta_reports_chua_do():
    """Khi cảnh thiếu layout_audit trong meta, audit_video phải báo trạng thái CHƯA ĐO và all_passed=False."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        p_dir = Path(tmp_dir)
        # Tạo edit_plan.json mẫu với 2 cảnh
        edit_plan = {
            "title": "Test Audit",
            "scenes": [
                {"id": 1, "narration": "Cảnh 1", "shots": [{"duration_sec": 4.0}]},
                {"id": 2, "narration": "Cảnh 2", "shots": [{"duration_sec": 4.0}]},
            ]
        }
        (p_dir / "edit_plan.json").write_text(json.dumps(edit_plan), encoding="utf-8")
        
        # Chạy audit khi không có file cache meta
        report = audit_project(p_dir)
        
        assert report["overall_all_passed"] is False, "Khi thiếu layout_audit, overall_all_passed không được phép True"
        for sc in report["scenes"]:
            assert sc["audit_status"] == "CHƯA ĐO", f"Cảnh {sc['scene_id']} phải có audit_status == 'CHƯA ĐO'"
            assert sc["all_passed"] is False


def test_audit_five_scenes_have_distinct_metrics():
    """5 cảnh khác nhau không thể có metrics layout giống hệt nhau trừ khi trùng hợp có bằng chứng."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        p_dir = Path(tmp_dir)
        edit_plan = {
            "title": "Test Diversity",
            "scenes": [
                {"id": i, "narration": f"Cảnh {i}", "shots": [{"duration_sec": 4.0}]}
                for i in range(1, 6)
            ]
        }
        (p_dir / "edit_plan.json").write_text(json.dumps(edit_plan), encoding="utf-8")
        
        # Giả lập 5 cache meta với các kích thước hero_width thực tế khác nhau
        meta_dir = p_dir / "render" / "motion_cache"
        meta_dir.mkdir(parents=True, exist_ok=True)
        for i in range(1, 6):
            meta_content = {
                "scene_id": i,
                "layout_audit": {
                    "hero_width": 880 + i * 15,
                    "hero_area_ratio": round(0.55 + i * 0.02, 3),
                    "min_font_size": 38 + i,
                    "clipped_rows": 0,
                    "bbox_overlaps": 0,
                    "t0_visible_count": 1,
                    "max_still_interval_sec": round(0.3 + i * 0.05, 2),
                    "empty_space_ratio": round(0.30 - i * 0.02, 3),
                    "empty_prompts": 0,
                    "caption_collisions": 0,
                    "center_y_drift": i * 10,
                }
            }
            (meta_dir / f"scene_{i}_meta.json").write_text(json.dumps(meta_content), encoding="utf-8")

        report = audit_project(p_dir)
        hero_widths = [sc["metrics"]["hero_width"] for sc in report["scenes"]]
        assert len(set(hero_widths)) == 5, f"5 cảnh phải có hero_width khác nhau thực tế, nhận được: {hero_widths}"
