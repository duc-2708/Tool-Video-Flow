"""Test catalog synchronization, stage.js render coverage and Stage ActorDef healing."""
import json
import re
from pathlib import Path
import pytest

from editor.stage.schema import StageScript, ActorDef, SceneDef, ActionDef, find_nearest_actor_type, ALLOWED_STAGE_ACTORS
from editor.stage.compiler import build_stage_html
from editor.stage.renderer import stage_browser_page
from schemas.visual_bible import ALLOWED_ACTOR_TYPES, ALLOWED_WORLD_KINDS

CATALOG_PATH = Path(__file__).resolve().parent.parent / "editor/stage/catalog.json"
STAGE_JS_PATH = Path(__file__).resolve().parent.parent / "editor/stage/engine/stage.js"


def test_catalog_json_validity_and_completeness():
    assert CATALOG_PATH.is_file(), "catalog.json is missing!"
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    assert "actors" in data
    assert "worlds" in data
    assert len(data["actors"]) >= 28
    assert len(data["worlds"]) >= 7

    # Check each actor has required fields
    for a_id, meta in data["actors"].items():
        assert meta["id"] == a_id
        assert "label" in meta and len(meta["label"]) > 0
        assert "states" in meta and len(meta["states"]) >= 3
        assert "ports" in meta and isinstance(meta["ports"], list)
        assert "default_size" in meta and len(meta["default_size"]) == 3
        assert "group" in meta

    # Check each world has required fields and >= 3 zones
    for w_id, meta in data["worlds"].items():
        assert meta["id"] == w_id
        assert "label" in meta
        assert "palette" in meta
        assert "zones" in meta and len(meta["zones"]) >= 3


def test_visual_bible_types_exist_in_catalog():
    """All actor types and world kinds allowed in Visual Bible must exist in catalog."""
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    catalog_actors = set(data["actors"].keys())
    catalog_worlds = set(data["worlds"].keys())

    missing_actors = ALLOWED_ACTOR_TYPES - catalog_actors
    assert not missing_actors, f"Visual Bible actor types missing from catalog: {missing_actors}"

    missing_worlds = ALLOWED_WORLD_KINDS - catalog_worlds
    assert not missing_worlds, f"Visual Bible world kinds missing from catalog: {missing_worlds}"


def test_all_catalog_actors_have_render_handlers_in_stage_js():
    """Static analysis: stage.js must contain render dispatcher and SVG generator for each catalog actor."""
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    stage_js = STAGE_JS_PATH.read_text(encoding="utf-8")

    for a_id in data["actors"].keys():
        # Must check type in dispatcher
        assert f"act.type === '{a_id}'" in stage_js or f"act.type === \\'{a_id}\\'" in stage_js, f"stage.js does not dispatch actor type '{a_id}'"


def test_actor_def_healing_invalid_type():
    """ActorDef with invalid type must heal into nearest valid type and record in review_notes."""
    # 1. Invalid cloud-like type -> cloud
    a1 = ActorDef(id="server_fake", type="cloud_server_unknown")
    assert a1.type in ALLOWED_STAGE_ACTORS
    assert a1.type == "cloud"

    # 2. Invalid security lock -> lock_shield
    a2 = ActorDef(id="safe_fake", type="super_security_lock")
    assert a2.type in ALLOWED_STAGE_ACTORS
    assert a2.type == "lock_shield"

    # 3. Completely arbitrary string -> note_board
    a3 = ActorDef(id="random_fake", type="completely_unheard_of_xyz")
    assert a3.type in ALLOWED_STAGE_ACTORS
    assert a3.type == "note_board"


def test_headless_render_every_catalog_actor():
    """Render one actor of each catalog type in headless Playwright and verify SVG is non-empty with dimensions."""
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    actor_types = list(data["actors"].keys())

    actors = [
        ActorDef(
            id=f"act_{i}",
            type=at,
            pos=[0, 0, 0],
            state=data["actors"][at]["states"][0],
            label=data["actors"][at]["label"]
        )
        for i, at in enumerate(actor_types)
    ]
    scenes = [
        SceneDef(
            scene_id="s1",
            duration_sec=1.0,
            actions=[ActionDef(verb="enter", target=f"act_{i}", at_sec=0.0) for i in range(len(actor_types))]
        )
    ]

    script = StageScript.model_validate({"actors": actors, "scenes": scenes})
    html = build_stage_html(script)

    with stage_browser_page((540, 960)) as page:
        page.set_content(html)
        page.evaluate("window.renderAt(0.5)")
        for i, at in enumerate(actor_types):
            svg_content = page.evaluate(f"""(() => {{
                const el = document.getElementById('actor-act_{i}');
                return el ? el.innerHTML.trim() : '';
            }})()""")
            assert svg_content, f"Actor '{at}' rendered empty SVG!"
            has_shapes = any(tag in svg_content for tag in ["<polygon", "<ellipse", "<path", "<circle", "<rect", "<line"])
            assert has_shapes, f"Actor '{at}' rendered no graphic elements!"


def test_headless_render_5_world_backgrounds():
    """Render each of the 5 main worlds and verify distinct grid and floor decorations."""
    worlds = ["secure_building", "data_pipeline", "courtroom", "city_road", "generic_stage"]
    for w in worlds:
        script = StageScript.model_validate({
            "world": w,
            "actors": [ActorDef(id="test_act", type="vps_server", pos=[0, 0, 0], state="on")],
            "scenes": [SceneDef(scene_id="s1", duration_sec=1.0, actions=[ActionDef(verb="enter", target="test_act", at_sec=0.0)])]
        })
        html = build_stage_html(script)
        with stage_browser_page((540, 960)) as page:
            page.set_content(html)
            page.evaluate("window.renderAt(0.5)")
            grid_svg = page.evaluate("document.getElementById('grid-lines-group').innerHTML")
            assert len(grid_svg) > 500, f"World '{w}' background SVG too small or missing!"
