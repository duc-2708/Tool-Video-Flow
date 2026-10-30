import re
from pathlib import Path
import pytest
from editor.motion.scheduler import (
    schedule_shots_no_repeat,
    build_shot_factual_data,
    validate_recipe_fit,
    enough_for_shot,
    _normalize_text,
)


def test_anti_hardcode_source_code():
    """Grep codebase to ensure no sample video entities/numbers are hardcoded."""
    root = Path(__file__).resolve().parent.parent  # video_ai_tool/
    allowed_dirs = {"tests", "fixtures", "output", "tools"}
    forbidden_terms = [
        "Ashley Paul Griffith",
        "Griffith",
        "202 tội danh",
        "ĐANG TẠM GIAM",
        "HOÃN XÉT XỬ",
        "Dấu hiệu bỏ qua",
        "New South Wales",
        "Brisbane",
    ]

    violations = []
    for ext in ("*.py", "*.js", "*.json", "*.yaml"):
        for path in root.rglob(ext):
            parts = path.relative_to(root).parts
            if any(p in allowed_dirs for p in parts) or any(p.startswith(".") for p in parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for term in forbidden_terms:
                if term.lower() in text.lower():
                    violations.append(f"{path.relative_to(root)}: contains '{term}'")

    assert not violations, "Phát hiện chuỗi dữ liệu mẫu bị hard-code trong mã nguồn:\n" + "\n".join(violations)


def test_scheduler_three_distinct_topics_grounded():
    """Run scheduler with 3 mock scripts across different domains (stocks, court, tech).
    Ensure:
    1. Zero sample video strings in any scheduled plan.
    2. Every label/stat on recipes is strictly grounded in that shot's narration.
    3. Anchor dynamically aligns with domain intent.
    """
    topics = {
        "stocks": {
            "shots": [
                {"narration": "Cổ phiếu Vinamilk tăng mạnh 15 phần trăm trong phiên giao dịch sáng nay.", "duration": 3.0},
                {"narration": "Khối ngoại gom ròng hơn 350 tỷ đồng cổ phiếu bán lẻ.", "duration": 3.0},
                {"narration": "Doanh thu xuất khẩu quý ba đạt kỷ lục mới nhờ thị trường tiêu thụ rộng lớn.", "duration": 3.0},
                {"narration": "Biên lợi nhuận gộp phục hồi đáng kể so với cùng kỳ năm trước.", "duration": 3.0},
                {"narration": "Nhà đầu tư theo dõi sát biến động chỉ số thị trường trước khi ra quyết định.", "duration": 3.0},
            ],
            "expected_anchor_keywords": ["thị trường", "chỉ số", "cột mốc"],
        },
        "legal": {
            "shots": [
                {"narration": "Tòa án nhân dân thành phố mở phiên tòa xét xử sơ thẩm vụ án kinh tế lớn.", "duration": 3.0},
                {"narration": "Hội đồng xét xử xem xét lời khai của các bị cáo và hồ sơ điều tra.", "duration": 3.0},
                {"narration": "Viện kiểm sát công bố bản cáo trạng dài hơn 80 trang với nhiều chứng cứ.", "duration": 3.0},
                {"narration": "Các luật sư bào chữa đề nghị làm rõ trách nhiệm của các đơn vị liên quan.", "duration": 3.0},
                {"narration": "Bản án dự kiến được tuyên vào cuối tuần sau khi nghị án.", "duration": 3.0},
            ],
            "expected_anchor_keywords": ["pháp lý", "hồ sơ", "cán cân"],
        },
        "tech": {
            "shots": [
                {"narration": "Hướng dẫn cài đặt môi trường lập trình Python và tối ưu hóa hiệu năng.", "duration": 3.0},
                {"narration": "Cấu hình biến môi trường và thiết lập máy chủ ảo trên đám mây.", "duration": 3.0},
                {"narration": "Kiểm tra mã nguồn tự động với công cụ phân tích tĩnh nhanh chóng.", "duration": 3.0},
                {"narration": "Triển khai ứng dụng container với Docker chỉ trong vài thao tác đơn giản.", "duration": 3.0},
                {"narration": "Theo dõi nhật ký hệ thống và đo thời gian phản hồi của dịch vụ.", "duration": 3.0},
            ],
            "expected_anchor_keywords": ["kỹ thuật", "hệ thống", "cấu trúc"],
        },
    }

    forbidden_sample_strings = [
        "ashley", "griffith", "202", "bảo vệ trẻ em", "giữ trẻ", "tạm giam", "brisbane", "australia"
    ]

    for topic_name, topic_data in topics.items():
        shots_input = [
            {
                "narration": s["narration"],
                "text": s["narration"],
                "duration": s["duration"],
                "duration_sec": s["duration"],
                "is_recap": (i == len(topic_data["shots"]) - 1),
            }
            for i, s in enumerate(topic_data["shots"])
        ]

        scheduled, notes = schedule_shots_no_repeat(shots_input, min_distinct=4, min_dist=2, max_freq=2)
        assert len(scheduled) == len(shots_input)

        # 1. Assert zero sample video strings in scheduled output
        plan_str = str(scheduled).lower()
        for fb in forbidden_sample_strings:
            if topic_name == "legal" and fb == "tạm giam":
                continue
            assert fb not in plan_str, f"Phát hiện rò rỉ chuỗi mẫu '{fb}' trong chủ đề '{topic_name}'!"

        # 2. Assert every label/item in data is grounded in that shot's narration
        for sh in scheduled:
            shot_text = sh.get("narration") or sh.get("text") or ""
            norm_shot = _normalize_text(shot_text)
            data = sh.get("data", {})

            for k in ["label", "text", "name", "target", "title", "left_label", "right_label"]:
                val = data.get(k)
                if val and isinstance(val, str):
                    words = [w for w in _normalize_text(val).split() if len(w) >= 2]
                    assert any(w in norm_shot for w in words), (
                        f"Nhãn '{val}' (trường '{k}') không có từ nào xuất hiện trong câu nói: '{shot_text}'"
                    )

            if "items" in data and isinstance(data["items"], list):
                for item in data["items"]:
                    if isinstance(item, str):
                        words = [w for w in _normalize_text(item).split() if len(w) >= 2]
                        assert any(w in norm_shot for w in words), (
                            f"Item '{item}' không có từ nào xuất hiện trong câu: '{shot_text}'"
                        )

            # Check fit validation
            assert validate_recipe_fit(sh["recipe"], data, shot_text, shot_text) is True

        # 3. Assert anchor reflects domain
        first_anchor = scheduled[0].get("anchor", {})
        meta_name = first_anchor.get("metaphor_name", "").lower()
        expected = topic_data["expected_anchor_keywords"]
        assert any(kw in meta_name for kw in expected), (
            f"Anchor metaphor '{meta_name}' không phản ánh đúng chủ đề '{topic_name}' (kỳ vọng chứa {expected})"
        )
