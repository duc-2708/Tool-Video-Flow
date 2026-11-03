"""Anti-hardcode source code check and topic grounding validation for Motion Kit v2."""
import re
from pathlib import Path
import pytest

from editor.motion.light_glass_slots import heuristic_slide_script_for_edit_plan
from schemas.edit_plan import EditPlan, Scene, Shot


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


def test_kit_v2_three_distinct_topics_grounded():
    """Verify Kit v2 heuristic mapper across stocks, legal, and tech topics."""
    topics = {
        "stocks": [
            "Cổ phiếu Vinamilk tăng mạnh 15% trong phiên sáng nay.",
            "Khối ngoại gom ròng hơn 350 tỷ đồng cổ phiếu bán lẻ.",
            "Doanh thu xuất khẩu quý ba đạt mức kỷ lục mới.",
            "Biên lợi nhuận gộp phục hồi mạnh so với cùng kỳ.",
        ],
        "legal": [
            "Tòa án mở phiên xét xử sơ thẩm vụ án kinh tế lớn.",
            "Hội đồng xét xử thẩm tra lời khai và hồ sơ điều tra.",
            "Viện kiểm sát công bố bản cáo trạng dài hơn 80 trang.",
            "Bản án dự kiến được tuyên vào tuần sau.",
        ],
        "tech": [
            "Hướng dẫn cài đặt môi trường lập trình Python.",
            "Cấu hình máy chủ ảo trên đám mây siêu tốc.",
            "Kiểm tra mã nguồn tự động với công cụ phân tích.",
            "Triển khai container với độ sẵn sàng đạt 99%.",
        ],
    }

    forbidden_sample_strings = ["ashley", "griffith", "202", "brisbane", "australia"]

    for topic_name, narrations in topics.items():
        scenes = [
            Scene(
                id=i + 1,
                narration=narr,
                role="explain",
                shots=[
                    Shot(
                        type="stock_video",
                        query=narr[:20],
                        duration_sec=5.0,
                        planning_duration=True,
                        effect="zoom_in",
                        text_overlay=None,
                    )
                ],
            )
            for i, narr in enumerate(narrations)
        ]
        plan = EditPlan(
            title=f"Chủ đề {topic_name}",
            format="tiktok",
            voice="vi-VN-NamMinhNeural",
            music={"mood": "calm", "volume": 0.08},
            scenes=scenes,
        )

        script = heuristic_slide_script_for_edit_plan(plan, total_duration=20.0)
        assert len(script.scenes) >= 3

        script_str = script.model_dump_json().lower()
        for fb in forbidden_sample_strings:
            assert fb not in script_str, f"Phát hiện rò rỉ '{fb}' trong chủ đề {topic_name}"

        # Layouts must be kit_*
        for sc in script.scenes:
            assert sc.layout.startswith("kit_"), f"Scene layout {sc.layout} does not start with kit_"
