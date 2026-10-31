"""Stage Gallery: Render all 28 actors across states and 5 worlds to 3s MP4 clips + contact sheets."""
import io
import json
import math
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Add repository root to sys.path
APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from editor.stage.schema import StageScript, ActorDef, SceneDef, ActionDef
from editor.stage.renderer import render_stage_script, stage_browser_page
from editor.stage.compiler import build_stage_html
from editor.captions import find_font

GALLERY_DIR = APP_DIR / "output/stage_gallery"
ACTORS_DIR = GALLERY_DIR / "actors"
WORLDS_DIR = GALLERY_DIR / "worlds"
THUMBS_DIR = GALLERY_DIR / "thumbs"

CATALOG_PATH = APP_DIR / "editor/stage/catalog.json"


def load_catalog():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_actor_script(actor_id: str, actor_meta: dict) -> StageScript:
    """Build a 3-second stage script showcasing the actor transitioning through 3 states."""
    states = actor_meta.get("states", ["default", "active", "alert"])
    st1 = states[0] if len(states) > 0 else "default"
    st2 = states[1] if len(states) > 1 else st1
    st3 = states[2] if len(states) > 2 else st2

    actor = ActorDef(
        id=actor_id,
        type=actor_id,
        pos=[0.0, 0.0, 0.0],
        state=st1,
        label=actor_meta.get("label", actor_id),
        sublabel=f"State: {st1}"
    )

    scenes = [
        SceneDef(
            scene_id="s1",
            duration_sec=3.0,
            title=f"Diễn viên: {actor_meta.get('label', actor_id)}",
            actions=[
                ActionDef(verb="enter", target=actor_id, at_sec=0.0, duration=0.4),
                ActionDef(verb="set_state", target=actor_id, at_sec=1.0, params={"state": st2}),
                ActionDef(verb="label", target=actor_id, at_sec=1.0, params={"sublabel": f"State: {st2}"}),
                ActionDef(verb="set_state", target=actor_id, at_sec=2.0, params={"state": st3}),
                ActionDef(verb="label", target=actor_id, at_sec=2.0, params={"sublabel": f"State: {st3}"}),
                ActionDef(verb="highlight", target=actor_id, at_sec=2.2, params={"color": "#00f5d4"}),
            ]
        )
    ]

    return StageScript(
        world="generic_stage",
        actors=[actor],
        scenes=scenes
    )


def build_world_script(world_id: str, world_meta: dict) -> StageScript:
    """Build a 3-second stage script showcasing the world environment and zone camera pans."""
    zones = world_meta.get("zones", [])
    actors = []
    # Place representative actors in zones if available
    if len(zones) >= 3:
        actors = [
            ActorDef(id="node_1", type="vps_server", pos=zones[0]["pos"], state="on", label=zones[0]["name"]),
            ActorDef(id="node_2", type="lock_shield", pos=zones[1]["pos"], state="locked", label=zones[1]["name"]),
            ActorDef(id="node_3", type="database_cylinder", pos=zones[2]["pos"], state="query", label=zones[2]["name"]),
        ]
    else:
        actors = [
            ActorDef(id="node_1", type="vps_server", pos=[0.0, 0.0, 0.0], state="on", label=world_meta.get("label", world_id))
        ]

    actions = [ActionDef(verb="enter", target=[a.id for a in actors], at_sec=0.0, duration=0.4)]
    if len(zones) >= 3:
        actions.append(ActionDef(verb="focus_camera", target="camera", at_sec=1.2, params={"x": 540 - 100, "y": 785 - 50, "zoom": 1.15}))
        actions.append(ActionDef(verb="focus_camera", target="camera", at_sec=2.2, params={"x": 540 + 100, "y": 785 + 50, "zoom": 1.0}))

    scenes = [
        SceneDef(
            scene_id="s1",
            duration_sec=3.0,
            title=f"Thế giới: {world_meta.get('label', world_id)}",
            actions=actions
        )
    ]

    return StageScript(
        world=world_id,
        actors=actors,
        scenes=scenes
    )


def render_all_gallery(scale: float = 0.5, fps: int = 15):
    """Render all 28 actors and 5 worlds, saving clips and composite contact sheet."""
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    ACTORS_DIR.mkdir(parents=True, exist_ok=True)
    WORLDS_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)

    catalog = load_catalog()
    actors_cat = catalog.get("actors", {})
    worlds_cat = catalog.get("worlds", {})

    print(f"=== Rendering Stage Gallery: {len(actors_cat)} Actors & {len(worlds_cat)} Worlds ===")
    thumbs = []

    # 1. Render Actors
    for a_id, a_meta in actors_cat.items():
        out_mp4 = ACTORS_DIR / f"{a_id}.mp4"
        thumb_path = THUMBS_DIR / f"actor_{a_id}.png"
        script = build_actor_script(a_id, a_meta)
        print(f"-> Rendering Actor: {a_id} ({a_meta.get('label')})...")
        render_stage_script(script, out_mp4, scale=scale, fps=fps)

        # Capture a crisp showcase frame at t=2.4s (state 3)
        html = build_stage_html(script)
        with stage_browser_page((int(1080 * scale), int(1920 * scale))) as page:
            page.set_content(html)
            page.evaluate("window.renderAt(2.4)")
            png_bytes = page.screenshot(type="png")
            thumb_path.write_bytes(png_bytes)
            thumbs.append((f"Actor: {a_id}", thumb_path))

    # 2. Render Worlds
    for w_id, w_meta in worlds_cat.items():
        out_mp4 = WORLDS_DIR / f"{w_id}.mp4"
        thumb_path = THUMBS_DIR / f"world_{w_id}.png"
        script = build_world_script(w_id, w_meta)
        print(f"-> Rendering World: {w_id} ({w_meta.get('label')})...")
        render_stage_script(script, out_mp4, scale=scale, fps=fps)

        # Capture frame at t=1.5s
        html = build_stage_html(script)
        with stage_browser_page((int(1080 * scale), int(1920 * scale))) as page:
            page.set_content(html)
            page.evaluate("window.renderAt(1.5)")
            png_bytes = page.screenshot(type="png")
            thumb_path.write_bytes(png_bytes)
            thumbs.append((f"World: {w_id}", thumb_path))

    # 3. Create Master Contact Sheet
    print(f"-> Creating master contact sheet for {len(thumbs)} items...")
    cols = 6
    rows = math.ceil(len(thumbs) / cols)
    cell_w, cell_h = 270, 480
    header_h = 40
    sheet_w = cols * cell_w
    sheet_h = rows * (cell_h + header_h)

    sheet_img = Image.new("RGB", (sheet_w, sheet_h), color=(10, 6, 25))
    draw = ImageDraw.Draw(sheet_img)
    font = ImageFont.load_default()

    for idx, (label, t_path) in enumerate(thumbs):
        col = idx % cols
        row = idx // cols
        x = col * cell_w
        y = row * (cell_h + header_h)

        if t_path.is_file():
            cell_img = Image.open(t_path).convert("RGB")
            cell_img = cell_img.resize((cell_w, cell_h), Image.Resampling.LANCZOS)
            sheet_img.paste(cell_img, (x, y + header_h))

        # Draw header text
        draw.rectangle([x, y, x + cell_w, y + header_h], fill=(22, 12, 48))
        draw.text((x + 10, y + 12), label, fill=(0, 245, 212), font=font)
        draw.rectangle([x, y, x + cell_w, y + cell_h + header_h], outline=(157, 78, 221), width=1)

    master_sheet_path = GALLERY_DIR / "contact_sheet_stage.png"
    sheet_img.save(master_sheet_path, "PNG")
    print(f"=== STAGE GALLERY COMPLETE: {master_sheet_path} ===")
    return master_sheet_path


if __name__ == "__main__":
    render_all_gallery(scale=0.25, fps=12)
