"""Tests for tools/rerender_with_theme.py."""
import json
from copy import deepcopy
from pathlib import Path

from schemas.assets import ResolvedEditPlan
from tests.test_director import fixture_plan
from tools.rerender_with_theme import rerender_project_with_theme
from utils.atomic_io import write_json_atomic


def test_rerender_dry_run_slide_script(tmp_path, monkeypatch):
    p_dir = tmp_path / "mock_project"
    p_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = p_dir / "audio"
    audio_dir.mkdir()
    clips_dir = p_dir / "clips"
    clips_dir.mkdir()

    raw_plan = fixture_plan()
    # Keep 5 scenes
    raw_plan["scenes"] = raw_plan["scenes"][:5]
    raw_plan["scenes"][0]["role"] = "hook"
    raw_plan["scenes"][-1]["role"] = "cta"
    for sc in raw_plan["scenes"]:
        sc_id = sc["id"]
        # Add numbers and Vietnamese narration for rich grounding
        sc["narration"] = f"Câu số {sc_id} với tốc độ tăng trưởng {sc_id * 10}% vượt bậc."
        # Create dummy mp3 and words
        (audio_dir / f"scene_{sc_id}.mp3").write_bytes(b"\x00" * 200)
        words = [
            {"text": "Câu", "start": 0.0, "end": 0.5},
            {"text": "số", "start": 0.5, "end": 0.9},
            {"text": str(sc_id), "start": 0.9, "end": 1.2},
            {"text": f"{sc_id * 10}%", "start": 1.2, "end": 2.0},
        ]
        (audio_dir / f"scene_{sc_id}.words.json").write_text(json.dumps({"words": words}), encoding="utf-8")

    raw_plan.update(
        source_plan_hash="fixture_hash",
        timing_basis="audio",
        warnings=[],
    )
    resolved_plan = ResolvedEditPlan.model_validate(raw_plan)
    write_json_atomic(p_dir / "edit_plan.resolved.json", resolved_plan.model_dump(mode="json"))

    brief = {
        "topic": "Dự án thử nghiệm công nghệ",
        "facts": [
            {
                "claim": "Tăng trưởng 10% đến 50%",
                "source_name": "TechNews",
                "source_url": "https://technews.vn/ai",
            }
        ]
    }
    write_json_atomic(p_dir / "brief.json", brief)

    # Mock run_render and measured_audio_duration to avoid full Playwright/FFmpeg render in quick unit test
    monkeypatch.setattr("editor.timeline.measured_audio_duration", lambda path: 5.0)
    monkeypatch.setattr("utils.media.measured_audio_duration", lambda path: 5.0)

    def mock_run_render(plan_path, *args, **kwargs):
        dest_path = Path(plan_path).parent / "render" / "mock_video.mp4"
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(b"\x00" * 1000)
        return {"status": "ok", "path": str(dest_path)}

    monkeypatch.setattr("tools.rerender_with_theme.run_render", mock_run_render)

    res = rerender_project_with_theme(
        project_dir=p_dir,
        theme="light_glass",
        use_slide_script=True,
        confirm_cost=False,  # deterministic offline mode
        scale=0.5,
        fps=30,
        run_audit=True,
    )
    assert res["project"] == str(p_dir)
    assert Path(p_dir / "slide_script.json").is_file()
    assert res["slide_script"] is not None
    assert len(res["slide_script"]["slides"]) == 5
    assert res["audit"]["passed"] is True
    assert res["audit"]["total_score"] >= 90
