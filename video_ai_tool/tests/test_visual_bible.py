"""Unit and regression tests for Visual Bible (Giai đoạn 8-W2a)."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from schemas.edit_plan import EditPlan, Scene, Shot
from schemas.visual_bible import (
    ALLOWED_ACTOR_TYPES,
    ALLOWED_WORLD_KINDS,
    VisualBible,
    VisualBibleStatus,
)
from agents.visual_bible import (
    create_visual_bible,
    generate_fallback_visual_bible,
    validate_and_heal_visual_bible,
    save_visual_bible,
)


def make_mock_plan(title: str, narrations: list[str]) -> EditPlan:
    scenes = []
    from schemas.edit_plan import Music
    for idx, text in enumerate(narrations, 1):
        shots = [
            Shot(
                type="text_card",
                query="illustration concept",
                duration_sec=3.0,
                effect="none",
                text_overlay=" ".join(text.split()[:4]),
                card_text=" ".join(text.split()[:4]),
            ),
            Shot(
                type="text_card",
                query="detail visual",
                duration_sec=3.0,
                effect="none",
                text_overlay=" ".join(text.split()[-3:]),
                card_text=" ".join(text.split()[-3:]),
            )
        ]
        role = "hook" if idx == 1 else ("cta" if idx == len(narrations) else "body")
        scenes.append(Scene(
            id=idx,
            role=role,
            narration=text,
            shots=shots,
            transition_out="cut",
            sfx="none"
        ))
    return EditPlan(
        title=title,
        format="tiktok",
        voice="vi-VN-NamMinhNeural",
        music=Music(mood="electronic", volume=0.5),
        scenes=scenes
    )


def test_visual_bible_schema():
    # Verify basic schema instantiation and constraints
    data = {
        "theme_name": "neon_dark",
        "worlds": [
            {
                "id": "w1",
                "kind": "secure_building",
                "reason": "Phù hợp để minh họa hạ tầng dữ liệu.",
                "zones": ["zone_1", "zone_2"]
            }
        ],
        "persistent_actors": [
            {
                "id": "act1",
                "type": "vps_server",
                "role": "Máy chủ chính",
                "states": ["normal", "alert"]
            }
        ],
        "structure": {
            "chapters": [
                {
                    "id": "c1",
                    "title": "Khởi đầu hệ thống",
                    "scene_ids": [1],
                    "kicker": "PHẦN 1/2"
                }
            ]
        },
        "progress_metaphor": {
            "type": "step_bar",
            "items": ["Bắt đầu", "Kết thúc"]
        },
        "concepts": [
            {
                "term": "Hạ tầng",
                "scene_id": 1,
                "sentence_index": 1,
                "world_zone": "zone_1",
                "actor_id": "act1",
                "evidence_sentence": "Hạ tầng mạng cần được nâng cấp."
            }
        ],
        "numbers_allowed": [100]
    }
    bible = VisualBible.model_validate(data)
    assert bible.theme_name == "neon_dark"
    assert len(bible.worlds) == 1
    assert bible.worlds[0].kind == "secure_building"
    assert len(bible.persistent_actors) == 1
    assert bible.persistent_actors[0].type == "vps_server"
    assert bible.structure.chapters[0].kicker == "PHẦN 1/2"
    assert bible.numbers_allowed == [100]


def test_visual_bible_llm_mock_success():
    # Mock LLM provider returning valid JSON
    plan = make_mock_plan(
        "Bảo mật đám mây doanh nghiệp",
        [
            "Doanh nghiệp áp dụng giải pháp bảo mật đám mây và tường lửa thông minh.",
            "Các kỹ sư rà soát mã nguồn và phát hiện 3 điểm yếu nghiêm trọng."
        ]
    )
    mock_json = {
        "theme_name": "neon_dark",
        "worlds": [
            {
                "id": "w_cloud",
                "kind": "data_pipeline",
                "reason": "Mô tả đường truyền mạng và đám mây dữ liệu.",
                "zones": ["inbound", "firewall", "storage"]
            }
        ],
        "persistent_actors": [
            {
                "id": "cloud_gateway",
                "type": "cloud",
                "role": "Cổng kết nối đám mây bảo mật",
                "states": ["online", "syncing"]
            }
        ],
        "structure": {
            "chapters": [
                {
                    "id": "ch1",
                    "title": "Bảo mật đám mây",
                    "scene_ids": [1, 2],
                    "kicker": "PHẦN 1/1"
                }
            ]
        },
        "progress_metaphor": {
            "type": "glass_fill",
            "items": ["Triển khai", "Hoàn tất"]
        },
        "concepts": [
            {
                "term": "Bảo mật đám mây",
                "scene_id": 1,
                "sentence_index": 1,
                "world_zone": "firewall",
                "actor_id": "cloud_gateway",
                "evidence_sentence": "Doanh nghiệp áp dụng giải pháp bảo mật đám mây và tường lửa thông minh."
            }
        ],
        "numbers_allowed": [3]
    }

    mock_provider = MagicMock()
    mock_provider.generate_json.return_value = mock_json

    bible, status = create_visual_bible(plan, provider=mock_provider)

    assert status.llm_ok is True
    assert status.fallback_used is False
    assert len(bible.worlds) == 1
    assert bible.worlds[0].kind == "data_pipeline"
    assert len(bible.persistent_actors) == 1
    assert bible.persistent_actors[0].type == "cloud"
    assert bible.concepts[0].term == "Bảo mật đám mây"
    assert 3 in bible.numbers_allowed


def test_visual_bible_llm_failure_fallback():
    # Mock LLM provider raising an exception -> must trigger fallback
    plan = make_mock_plan(
        "Vụ án gian lận tài chính tại tòa án",
        [
            "Tòa án mở phiên xét xử vụ án gian lận tài chính quy mô lớn.",
            "Hội đồng xét xử xem xét các chứng cứ và hồ sơ pháp lý."
        ]
    )
    mock_provider = MagicMock()
    mock_provider.generate_json.side_effect = RuntimeError("API Rate Limit Exceeded")

    bible, status = create_visual_bible(plan, provider=mock_provider)

    assert status.llm_ok is False
    assert status.fallback_used is True
    assert "Rate Limit" in status.reason
    assert len(bible.worlds) >= 1
    # Check that fallback inferred courtroom from legal keywords
    assert bible.worlds[0].kind == "courtroom"
    assert len(bible.persistent_actors) >= 1
    assert bible.persistent_actors[0].type == "note_board"
    assert len(bible.structure.chapters) >= 1
    assert bible.structure.chapters[0].kicker.startswith("PHẦN ")


def test_visual_bible_validator_heals_invalid_world_actor_and_removes_ungrounded_concepts():
    plan = make_mock_plan(
        "Kế hoạch nâng cấp mạng nội bộ",
        [
            "Hệ thống máy chủ công ty cần được nâng cấp định kỳ.",
            "Kỹ sư mạng thiết lập tường lửa mới để chặn mã độc."
        ]
    )

    invalid_bible_data = {
        "worlds": [
            {"id": "w1", "kind": "super_fancy_spaceship", "reason": "Tàu vũ trụ", "zones": ["deck1"]},
            {"id": "w2", "kind": "cyber_matrix", "reason": "Ma trận số", "zones": ["core"]},
            {"id": "w3", "kind": "lab", "reason": "Phòng lab phụ", "zones": ["sub"]}  # 3 worlds > 2 max
        ],
        "persistent_actors": [
            {"id": "a1", "type": "alien_robot", "role": "Robot ngoài hành tinh", "states": ["on"]},
            {"id": "a2", "type": "quantum_core", "role": "Lõi lượng tử", "states": ["spin"]},
            {"id": "a3", "type": "laser_blaster", "role": "Súng laser", "states": ["fire"]},
            {"id": "a4", "type": "laptop", "role": "Máy tính", "states": ["open"]}  # 4 actors > 3 max
        ],
        "structure": {
            "chapters": [
                {
                    "id": "c1",
                    "title": "Tiêu đề này dài hơn rất nhiều so với quy định năm từ cho phép",
                    "scene_ids": [1],
                    "kicker": "PHAN_1"
                }
            ]
        },
        "progress_metaphor": {"type": "unknown_metaphor", "items": ["a"]},
        "concepts": [
            {
                "term": "Hệ thống máy chủ",
                "scene_id": 1,
                "evidence_sentence": "Hệ thống máy chủ công ty cần được nâng cấp định kỳ."
            },
            {
                "term": "Bánh mì kẹp thịt",  # Hallucinated term completely absent from script
                "scene_id": 1,
                "evidence_sentence": "Ăn bánh mì kẹp thịt rất ngon."
            }
        ],
        "numbers_allowed": [999999]  # Not present in script
    }

    bible, notes = validate_and_heal_visual_bible(invalid_bible_data, plan)

    # 1. Worlds healed: invalid kinds mapped to generic_stage, capped to 2
    assert len(bible.worlds) == 2
    assert all(w.kind in ALLOWED_WORLD_KINDS for w in bible.worlds)

    # 2. Actors healed: invalid types mapped to note_board, capped to 3
    assert len(bible.persistent_actors) == 3
    assert all(a.type in ALLOWED_ACTOR_TYPES for a in bible.persistent_actors)

    # 3. Chapter title truncated to <= 5 words
    chap = bible.structure.chapters[0]
    assert len(chap.title.split()) <= 5
    assert chap.kicker.startswith("PHẦN ")

    # 4. Progress metaphor healed
    assert bible.progress_metaphor.type in {"none", "glass_fill", "step_bar", "stack_up"}

    # 5. Hallucinated concept removed
    terms = [c.term for c in bible.concepts]
    assert "Hệ thống máy chủ" in terms
    assert "Bánh mì kẹp thịt" not in terms, "Hallucinated concept must be removed!"


def test_three_distinct_mock_topics_produce_different_worlds_and_no_leakage():
    # 1. Cybersecurity script
    plan_sec = make_mock_plan(
        "Bão Lỗ Hổng Và Nguy Cơ Tấn Công Máy Chủ",
        [
            "Lỗ hổng bảo mật nghiêm trọng đe dọa các máy chủ dữ liệu toàn cầu.",
            "Hacker khai thác điểm yếu để xâm nhập mạng nội bộ trái phép."
        ]
    )
    bible_sec = generate_fallback_visual_bible(plan_sec)

    # 2. Courtroom / Legal script
    plan_legal = make_mock_plan(
        "Phiên Tòa Xét Xử Đại Án Kinh Tế",
        [
            "Tòa án mở phiên xét xử sơ thẩm đối với các bị cáo trong vụ án lừa đảo.",
            "Đại diện viện kiểm sát công bố bản cáo trạng với nhiều bằng chứng."
        ]
    )
    bible_legal = generate_fallback_visual_bible(plan_legal)

    # 3. AI / Code Technical Guide
    plan_ai = make_mock_plan(
        "Hướng Dẫn Triển Khai AI Agent Tự Động",
        [
            "Kỹ sư phần mềm phát triển tác nhân trí tuệ nhân tạo bằng mã nguồn mở.",
            "Mô hình AI tự động thực thi các lệnh terminal và xử lý dữ liệu phức tạp."
        ]
    )
    bible_ai = generate_fallback_visual_bible(plan_ai)

    # Verify world differentiation
    assert bible_sec.worlds[0].kind == "secure_building"
    assert bible_legal.worlds[0].kind == "courtroom"
    assert bible_ai.worlds[0].kind == "lab"

    # Verify actor differentiation
    assert bible_sec.persistent_actors[0].type in {"vps_server", "lock_shield"}
    assert bible_legal.persistent_actors[0].type == "note_board"
    assert bible_ai.persistent_actors[0].type == "terminal_window"

    # Verify absolute anti-hardcode: no leakages from old sample videos
    forbidden_tokens = ["griffith", "binance", "artemis", "bioware", "brisbane", "202 toi danh", "tam giam"]
    for b in [bible_sec, bible_legal, bible_ai]:
        dumped_str = json.dumps(b.model_dump(mode="json"), ensure_ascii=False).lower()
        for tok in forbidden_tokens:
            assert tok not in dumped_str, f"Forbidden legacy token '{tok}' leaked into Visual Bible!"


def test_real_project_visual_bible_file():
    # Verify that output/auto-cong-nghe-e97dccbd contains valid visual_bible.json and visual_bible_status.json
    pdir = Path(__file__).resolve().parent.parent / "output" / "auto-cong-nghe-e97dccbd"
    bible_file = pdir / "visual_bible.json"
    status_file = pdir / "visual_bible_status.json"

    assert bible_file.is_file(), "visual_bible.json must exist in project directory"
    assert status_file.is_file(), "visual_bible_status.json must exist in project directory"

    b_data = json.load(open(bible_file, encoding="utf-8"))
    s_data = json.load(open(status_file, encoding="utf-8"))

    bible = VisualBible.model_validate(b_data)
    status = VisualBibleStatus.model_validate(s_data)

    assert len(bible.worlds) <= 2
    assert len(bible.persistent_actors) <= 3
    assert len(bible.structure.chapters) >= 1
    assert all(ch.kicker.startswith("PHẦN ") for ch in bible.structure.chapters)
    assert 84 in bible.numbers_allowed
    assert status.timestamp != ""
