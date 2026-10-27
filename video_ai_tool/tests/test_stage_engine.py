"""Unit and integration tests for Stage Engine (Giai đoạn 5a)."""
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
    assert len(script.actors) >= 4
    assert len(script.scenes) >= 2
    assert script.scenes[0].actions[0].verb == "enter"

    # Export JSON Schema
    schema = StageScript.export_json_schema()
    assert "properties" in schema
    assert "actors" in schema["properties"]
    assert "scenes" in schema["properties"]


def test_stage_compiler_and_actor_persistence():
    """Verify actor persistence: actors from scene 1 persist into scene 2 without recreation."""
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


def test_stage_html_compilation():
    """Verify build_stage_html inlines CSS and JS completely without template placeholders."""
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    script = StageScript.model_validate(data)
    html = build_stage_html(script)

    assert "__STAGE_CSS__" not in html
    assert "__STAGE_SCRIPT__" not in html
    assert "__STAGE_JS__" not in html
    assert "neon_purple" in html
    assert "laptop_client" in html


def test_stage_browser_render_at_and_audit():
    """Verify headless Chromium executes renderAt(t) deterministically and satisfies layout audit."""
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    script = StageScript.model_validate(data)
    html = build_stage_html(script)

    with stage_browser_page((540, 960)) as page:
        page.set_content(html, wait_until="load")
        page.evaluate("() => document.fonts.ready")

        # Test t=0
        state0 = page.evaluate("() => window.renderAt(0)")
        assert state0["t"] == 0
        assert state0["step_index"] == 0

        # Test t=4.0 (laptop typing, packet flying)
        state4 = page.evaluate("() => window.renderAt(4.0)")
        assert state4["t"] == 4.0
        assert state4["packet_flying"] is True

        # Test layout audit
        audit = page.evaluate("() => window.getLayoutAudit()")
        assert audit["step_title_compliant"] is True, f"Step title font size failed: {audit}"
        assert audit["label_font_compliant"] is True, f"Actor label font size failed: {audit}"
        assert audit["sublabel_font_compliant"] is True, f"Sublabel font size failed: {audit}"


def test_stage_engine_setting_default_false():
    """Verify STAGE_ENGINE_ENABLED defaults to False."""
    s = Settings()
    assert s.stage_engine_enabled is False
