"""Compiler and normalizer for Stage Engine DSL scripts."""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from editor.stage.schema import ActionDef, ActorDef, SceneDef, StageScript
from utils.word_timing import align_words, read_words

STAGE_DIR = Path(__file__).resolve().parent
ENGINE_DIR = STAGE_DIR / "engine"


def load_engine_assets() -> Tuple[str, str, str]:
    """Load stage.html, stage.css, stage.js."""
    html_template = (ENGINE_DIR / "stage.html").read_text(encoding="utf-8")
    css = (ENGINE_DIR / "stage.css").read_text(encoding="utf-8")
    js = (ENGINE_DIR / "stage.js").read_text(encoding="utf-8")
    return html_template, css, js


def normalize_at_phrase(action: ActionDef, words: List[Dict[str, Any]], scene_start: float, scene_duration: float) -> float:
    """Normalize action.at_phrase against words.json; fallback to at_sec or proportional timing."""
    if not action.at_phrase or not words:
        return action.at_sec

    phrase_clean = action.at_phrase.strip().lower()
    for w in words:
        w_text = str(w.get("text", "")).strip().lower().strip(" .,:;!?…")
        if phrase_clean in w_text or w_text in phrase_clean:
            return float(w.get("start", action.at_sec))

    # Fallback to current at_sec clamped to scene duration
    return min(action.at_sec, scene_duration - 0.2)


KNOWN_VERBS = {
    "enter", "exit", "move_to", "set_state", "connect", "send_packet",
    "type", "check", "open", "close", "highlight", "focus_camera",
    "pan", "blur_dissolve", "glitch", "stamp", "morph_to", "label"
}

VERB_ALIASES = {
    "zoom": "focus_camera",
    "write": "type",
    "show": "enter",
    "hide": "exit",
    "glow": "highlight",
    "pulse": "highlight",
    "fade_in": "enter",
    "fade_out": "exit",
    "morph": "morph_to"
}


def compile_stage_script(
    script: StageScript,
    words_data: Optional[Dict[str, List[Dict[str, Any]]]] = None
) -> StageScript:
    """Validate and compile StageScript actions, normalizing at_phrase and verifying actor persistence."""
    words_data = words_data or {}
    actor_ids = {a.id for a in script.actors}
    review_notes = []

    # Verify actions target existing actors and verbs are valid
    for sc in script.scenes:
        # Camera zoom constraint (<= 1.25)
        if sc.camera and sc.camera.zoom > 1.25:
            review_notes.append(f"Scene {sc.scene_id}: camera zoom {sc.camera.zoom} exceeds 1.25; clamped to 1.25.")
            sc.camera.zoom = 1.25

        scene_words = words_data.get(str(sc.scene_id), [])
        valid_actions = []
        for act in sc.actions:
            # Normalize at_phrase
            if act.at_phrase:
                act.at_sec = normalize_at_phrase(act, scene_words, 0.0, sc.duration_sec)

            # Check verb
            if act.verb not in KNOWN_VERBS:
                if act.verb in VERB_ALIASES:
                    mapped = VERB_ALIASES[act.verb]
                    review_notes.append(f"Scene {sc.scene_id}: mapped unknown verb '{act.verb}' to '{mapped}'.")
                    act.verb = mapped
                    valid_actions.append(act)
                else:
                    review_notes.append(f"Scene {sc.scene_id}: dropped invalid verb '{act.verb}'.")
                    continue
            else:
                valid_actions.append(act)

            # Check target actor exists if target is not a station or HUD element
            targets = [act.target] if isinstance(act.target, str) else act.target
            for tgt in targets:
                if not tgt.startswith("step_") and not tgt.startswith("station_") and tgt not in actor_ids and act.verb not in {"focus_camera", "pan", "blur_dissolve", "glitch", "stamp"}:
                    review_notes.append(f"Scene {sc.scene_id}: target actor '{tgt}' not in actors list.")

        sc.actions = valid_actions

    return script


def build_stage_html(script: StageScript) -> str:
    """Build standalone self-contained HTML for Playwright capture with embedded catalog."""
    html_template, css, js = load_engine_assets()
    script_json = script.model_dump_json()

    catalog_path = STAGE_DIR / "catalog.json"
    catalog_json = catalog_path.read_text(encoding="utf-8") if catalog_path.is_file() else "{}"

    html = html_template.replace("__STAGE_CSS__", css)
    html = html.replace("__STAGE_CATALOG__", catalog_json)
    html = html.replace("__STAGE_SCRIPT__", script_json)
    html = html.replace("__STAGE_JS__", js)
    return html
