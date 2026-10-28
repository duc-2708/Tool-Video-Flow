"""Unit and integration tests for Stage Engine (Giai đoạn 5a - Bước 2)."""
import json
from pathlib import Path
import pytest

from config.settings import Settings
from editor.stage.schema import StageScript, ActorDef, ActionDef, SceneDef
from editor.stage.compiler import compile_stage_script, build_stage_html
from editor.stage.renderer import stage_browser_page

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures/stage_demo_deploy_vps.json"


def test_stage_script_schema_validation():
    """Verify acceptance fixture conforms to StageScript Pydantic model and exports JSON Schema."""
    assert FIXTURE_PATH.is_file(), f"Fixture missing: {FIXTURE_PATH}"
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    script = StageScript.model_validate(data)

    assert len(script.hud.steps) == 5
    assert len(script.actors) >= 8
    assert len(script.scenes) >= 6
    assert script.scenes[0].actions[0].verb == "enter"

    # Export JSON Schema
    schema = StageScript.export_json_schema()
    assert "properties" in schema
    assert "actors" in schema["properties"]
    assert "scenes" in schema["properties"]


def test_stage_compiler_and_actor_persistence():
    """Verify actor persistence: actors from scene 1 persist into scene 2+ without recreation."""
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    script = StageScript.model_validate(data)
    compiled = compile_stage_script(script)

    actor_ids = {a.id for a in compiled.actors}
    assert "laptop_client" in actor_ids
    assert "vps_server" in actor_ids

    # Scene 2 targets laptop_client without re-entering
    sc2_actions = compiled.scenes[1].actions
    assert any(a.target == "laptop_client" and a.verb == "type" for a in sc2_actions)
    assert not any(a.target == "laptop_client" and a.verb == "enter" for a in sc2_actions)


def test_stage_morph_tracker_to_road():
    """Verify recap scene triggers morph of HUD tracker to 3D road with milestones."""
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    script = StageScript.model_validate(data)
    html = build_stage_html(script)

    with stage_browser_page((540, 960)) as page:
        page.set_content(html, wait_until="load")
        page.evaluate("() => document.fonts.ready")

        # Step 1: not road recap
        state1 = page.evaluate("() => window.renderAt(3.0)")
        assert state1["is_road_recap"] is False

        # Recap scene (last 6 seconds): road recap active
        total_dur = sum(s["duration_sec"] for s in data["scenes"])
        state_recap = page.evaluate(f"() => window.renderAt({total_dur - 2.0})")
        assert state_recap["is_road_recap"] is True

        # Check DOM contains road-recap-group and milestones
        has_road = page.evaluate("() => !!document.getElementById('road-recap-group')")
        assert has_road is True


def test_stage_send_packet_along_curve():
    """Verify send_packet executes along bezier curve between connection endpoints."""
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    script = StageScript.model_validate(data)
    html = build_stage_html(script)

    with stage_browser_page((540, 960)) as page:
        page.set_content(html, wait_until="load")
        page.evaluate("() => document.fonts.ready")

        # At t=4.2s (during packet transit in scene 1)
        st = page.evaluate("() => window.renderAt(4.2)")
        assert st["packet_flying"] is True
        assert st["cable_connected"] is True

        # Verify packet element exists in DOM
        has_packet = page.evaluate("() => document.querySelectorAll('.packet-capsule').length > 0")
        assert has_packet is True


def test_stage_deterministic_seek():
    """Verify seek(t) is strictly deterministic: calling renderAt(t) twice yields identical DOM state."""
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    script = StageScript.model_validate(data)
    html = build_stage_html(script)

    with stage_browser_page((540, 960)) as page:
        page.set_content(html, wait_until="load")
        page.evaluate("() => document.fonts.ready")

        # Evaluate at t=8.5s
        page.evaluate("() => window.renderAt(8.5)")
        html_first = page.evaluate("() => document.getElementById('actors-layer').innerHTML")

        # Jump away to t=1.0s then seek back to t=8.5s
        page.evaluate("() => window.renderAt(1.0)")
        page.evaluate("() => window.renderAt(8.5)")
        html_second = page.evaluate("() => document.getElementById('actors-layer').innerHTML")

        assert html_first == html_second, "Seek(t) must be strictly deterministic!"


def test_stage_blur_dissolve_and_glitch_preserve_layout():
    """Verify blur_dissolve and glitch trigger without distorting font size and boundary safety."""
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    script = StageScript.model_validate(data)
    html = build_stage_html(script)

    with stage_browser_page((540, 960)) as page:
        page.set_content(html, wait_until="load")
        page.evaluate("() => document.fonts.ready")

        # At scene_error_fix (around t=26.5s)
        # Find start time of scene_error_fix
        acc = 0.0
        err_start = 0.0
        for sc in data["scenes"]:
            if sc["scene_id"] == "scene_error_fix":
                err_start = acc
                break
            acc += sc["duration_sec"]

        # Glitch active at err_start + 0.3s
        page.evaluate(f"() => window.renderAt({err_start + 0.3})")
        has_glitch = page.evaluate("() => document.getElementById('world-viewport').classList.contains('glitch-active')")
        assert has_glitch is True

        # Layout audit must still satisfy typography and bounds
        audit = page.evaluate("() => window.getLayoutAudit()")
        assert audit["step_title_compliant"] is True
        assert audit["min_heading_font_size"] >= 56


def test_stage_unknown_verb_and_actor_aliases():
    """Verify compiler maps known aliases and drops unknown verbs with review notes without breaking."""
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    data["scenes"][0]["actions"].append({
        "at_sec": 3.0,
        "verb": "write",  # Alias for "type"
        "target": "laptop_client",
        "params": {"text": "echo hello"}
    })
    data["scenes"][0]["actions"].append({
        "at_sec": 4.0,
        "verb": "unknown_nonsense_action",  # Invalid verb
        "target": "laptop_client"
    })
    script = StageScript.model_validate(data)
    compiled = compile_stage_script(script)

    actions = compiled.scenes[0].actions
    verbs = [a.verb for a in actions]
    assert "type" in verbs
    assert "unknown_nonsense_action" not in verbs


def test_stage_engine_setting_default_false():
    """Verify STAGE_ENGINE_ENABLED defaults to False."""
    s = Settings()
    assert s.stage_engine_enabled is False
