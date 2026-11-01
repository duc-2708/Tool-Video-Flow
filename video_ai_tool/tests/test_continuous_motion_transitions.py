"""Unit tests for continuous motion frames, smooth shot transitions and visible narrative continuity."""
import pytest
from pathlib import Path
from schemas.motion_scene import MotionScenePlan
from editor.motion.scheduler import (
    schedule_shots_no_repeat,
    TRANSITION_TYPES,
)


def test_motion_scene_plan_supports_transition():
    """Verify MotionScenePlan schema accepts transition field and preserves hash exclusion when None."""
    plan = MotionScenePlan(scene_type="slot_counter", transition="directional_wipe")
    assert plan.transition == "directional_wipe"

    plan_default = MotionScenePlan(scene_type="balance_scale")
    assert plan_default.transition is None
    # Excluded when None to preserve hash integrity
    assert "transition" not in plan_default.model_dump(exclude_none=True)


def test_continuous_motion_beats_and_storyline_anchors():
    """Verify schedule_shots_no_repeat generates rich continuous motion beats and storyline-linked anchor states."""
    shots = [
        {"narration": "Mở đầu câu chuyện an ninh mạng với cảnh báo nguy cơ nghiêm trọng", "text": "Cảnh báo an ninh mạng", "duration": 4.5},
        {"narration": "Khai thác lỗ hổng bảo mật tấn công vào hệ thống máy chủ toàn cầu", "text": "Khai thác lỗ hổng", "duration": 3.6},
        {"narration": "Các chuyên gia đối chiếu giải pháp trước và sau khi triển khai bản vá", "text": "Trước và sau bản vá", "duration": 3.8},
        {"narration": "Mạng lưới giám sát tự động kích hoạt chế độ phòng thủ an toàn", "text": "Mạng lưới giám sát", "duration": 4.8},
        {"narration": "Tổng kết lại các bài học và khuyến nghị an toàn thông tin cốt lõi", "text": "Tổng kết khuyến nghị", "duration": 4.2, "is_recap": True},
    ]

    scheduled, _ = schedule_shots_no_repeat(shots, min_distinct=4, min_dist=2, max_freq=2)

    assert len(scheduled) == len(shots)

    # 1. Continuous motion beats check
    for sh in scheduled:
        beats = sh["beats"]
        assert len(beats) >= 4, f"Shot {sh['recipe']} should have >= 4 beats for duration {sh['duration']}"
        actions = [b["action"] for b in beats]
        assert any("enter_" in a for a in actions)
        assert any("action_" in a for a in actions)
        assert any("micro_stream_" in a for a in actions)
        assert any("impact_" in a for a in actions)

    # 2. Storyline-linked visible anchor states
    assert "Mở màn & Bối cảnh" in scheduled[0]["anchor"]["state"]
    assert "Tổng kết & Khuyến nghị" in scheduled[-1]["anchor"]["state"]
    for i, sh in enumerate(scheduled):
        assert f"Phần {i+1}/{len(shots)}" in sh["anchor"]["state"]

    # 3. Seamless transitions check
    transitions = [s["transition"] for s in scheduled]
    for i in range(len(transitions) - 1):
        assert transitions[i] != transitions[i+1], f"Transitions should not repeat consecutively: {transitions}"
        assert transitions[i] in TRANSITION_TYPES


def test_engine_and_runtime_contain_living_canvas_and_transitions():
    """Verify engine.js and runtime.js contain Living Canvas and shot transition code."""
    root = Path(__file__).resolve().parents[1]
    engine_js = (root / "editor/motion/scenes/engine.js").read_text(encoding="utf-8")
    runtime_js = (root / "editor/motion/runtime.js").read_text(encoding="utf-8")

    # Living Canvas micro-motions in engine.js
    assert "living-light-sweep" in engine_js
    assert "ambientY" in engine_js
    assert "ambientScale" in engine_js
    assert "transStyle" in engine_js
    assert "directional_wipe" in engine_js
    assert "zoom_through" in engine_js
    assert "morph_anchor" in engine_js

    # Seamless shot transitions in runtime.js
    assert "illustration.style.opacity" in runtime_js
    assert "curAnchor" in runtime_js
    assert "anchor-badge" in runtime_js
