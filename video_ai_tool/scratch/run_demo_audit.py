import sys
import os
sys.path.insert(0, os.path.abspath("."))
import json
from pathlib import Path
from schemas.slide_script import SlideScript, SlideItem, EmphasisItem, SourceRef
from tools.audit_style import audit_light_glass_project

demo_dir = Path("output/light_glass_demo")

brief = {
    "topic": "Kiến trúc vi xử lý thế hệ mới",
    "facts": [
        {"claim": "Hiệu năng xử lý các tác vụ trí tuệ nhân tạo tăng vọt 78% so với thế hệ trước.", "source_name": "The Verge", "source_url": "https://theverge.com"},
        {"claim": "Thế hệ mới mang tới 24 nhân xử lý so với 14 nhân của thế hệ cũ.", "source_name": "The Verge", "source_url": "https://theverge.com"},
        {"claim": "Ba điểm nâng cấp mấu chốt bao gồm băng thông mở rộng, tiết kiệm pin.", "source_name": "The Verge", "source_url": "https://theverge.com"}
    ],
    "key_numbers": [{"text": "78%"}, {"text": "24 nhân"}, {"text": "14 nhân"}, {"text": "3 điểm"}]
}
(demo_dir / "brief.json").write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")

slides = [
    SlideItem(
        id="slide_1",
        layout="lg_source_headline",
        sentence_ids=[1],
        slots={
            "pill": "THE VERGE",
            "title": "Kiến trúc vi xử lý mới đạt đột phá",
            "text": "Kiến trúc chip xử lý thế hệ mới vừa được công bố với quy trình đóng gói tiên tiến."
        },
        source_ref=SourceRef(url="https://theverge.com", domain="theverge.com", image_kind="card"),
        emphasis=[EmphasisItem(phrase="tiên tiến", kind="term")],
        t_start=0.0,
        t_end=6.0,
        duration=6.0,
        narration="Kiến trúc chip xử lý thế hệ mới vừa được công bố với quy trình đóng gói tiên tiến."
    ),
    SlideItem(
        id="slide_2",
        layout="lg_stat_hero",
        sentence_ids=[2],
        slots={
            "label": "HIỆU NĂNG TÁC VỤ AI",
            "value": 78,
            "unit": "%",
            "text": "Hiệu năng xử lý các tác vụ trí tuệ nhân tạo tăng vọt 78% so với thế hệ tiền nhiệm."
        },
        emphasis=[EmphasisItem(phrase="78%", kind="number")],
        t_start=6.0,
        t_end=12.0,
        duration=6.0,
        narration="Hiệu năng xử lý các tác vụ trí tuệ nhân tạo tăng vọt 78% so với thế hệ tiền nhiệm."
    ),
    SlideItem(
        id="slide_3",
        layout="lg_shot_features",
        sentence_ids=[3],
        slots={
            "title": "3 ĐIỂM NÂNG CẤP",
            "items": [
                "Băng thông bộ nhớ mở rộng gấp đôi cho AI",
                "Tiêu thụ năng lượng giảm 35% tiết kiệm pin",
                "Tương thích hoàn toàn hệ điều hành hiện nay"
            ]
        },
        emphasis=[EmphasisItem(phrase="mở rộng", kind="term")],
        t_start=12.0,
        t_end=19.0,
        duration=7.0,
        narration="Ba điểm nâng cấp mấu chốt bao gồm băng thông mở rộng, tiết kiệm pin và hỗ trợ toàn diện."
    ),
    SlideItem(
        id="slide_4",
        layout="lg_vs_compare",
        sentence_ids=[4],
        slots={
            "left": {"label": "CŨ 14 NHÂN", "text": "Thế hệ cũ 14 nhân"},
            "right": {"label": "MỚI 24 NHÂN", "text": "Thế hệ mới 24 nhân"}
        },
        emphasis=[EmphasisItem(phrase="24 nhân", kind="number")],
        t_start=19.0,
        t_end=26.0,
        duration=7.0,
        narration="So với thế hệ cũ chỉ có 14 nhân, thế hệ mới mang tới 24 nhân xử lý với điện áp tối ưu."
    ),
    SlideItem(
        id="slide_5",
        layout="lg_note_card",
        sentence_ids=[5],
        slots={
            "chip": "GHI CHÚ CHUYÊN GIA",
            "text": "Giới chuyên gia nhận định đây là bước nhảy vọt quan trọng nhất của ngành phần cứng năm nay."
        },
        emphasis=[EmphasisItem(phrase="bước nhảy vọt", kind="term")],
        t_start=26.0,
        t_end=32.0,
        duration=6.0,
        narration="Giới chuyên gia nhận định đây là bước nhảy vọt quan trọng nhất của ngành phần cứng năm nay."
    ),
    SlideItem(
        id="slide_6",
        layout="lg_cta_profile",
        sentence_ids=[6],
        slots={
            "channel_name": "TIN CÔNG NGHỆ",
            "pill": "ĐĂNG KÝ KÊNH",
            "text": "Theo dõi kênh để đón nhận các thông tin công nghệ và trí tuệ nhân tạo cập nhật mỗi ngày."
        },
        emphasis=[EmphasisItem(phrase="công nghệ", kind="term")],
        t_start=32.0,
        t_end=38.0,
        duration=6.0,
        narration="Theo dõi kênh để đón nhận các thông tin công nghệ và trí tuệ nhân tạo cập nhật mỗi ngày."
    ),
]

script = SlideScript(
    topic="Kiến trúc vi xử lý mới",
    total_duration=38.0,
    slides=slides,
    repair_notes=[]
)

(demo_dir / "slide_script.json").write_text(json.dumps(script.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")

# Run audit with actual video!
video_file = demo_dir / "light_glass_demo.mp4"
audit_res = audit_light_glass_project(demo_dir, video_path=video_file, slide_script=script)
print("AUDIT RESULT:")
print(json.dumps(audit_res, ensure_ascii=False, indent=2))
