"""Schema and normalizer for Visual Planner (Prompt B)."""
from typing import Literal, Any
from pydantic import Field
from schemas.base import StrictModel
from schemas.motion_scene import SceneCamera


class ElementEnter(StrictModel):
    at_phrase: str = ""
    anim: Literal["slide_up", "pop", "draw", "fill", "type", "count_up"] = "pop"
    at_sec: float | None = None


class ElementExit(StrictModel):
    at_phrase: str = "scene_end"
    anim: Literal["fade", "slide_down", "pop_out"] = "fade"
    at_sec: float | None = None


class VisualElement(StrictModel):
    id: str
    type: str
    zone: Literal["top", "middle", "bottom", "left", "right", "center"] = "center"
    content: dict[str, Any] = Field(default_factory=dict)
    evidence: str = ""
    no_numbers: bool = False
    enter: ElementEnter = Field(default_factory=ElementEnter)
    exit: ElementExit = Field(default_factory=ElementExit)
    motion_recipe: str | None = None
    variant_index: int | None = None
    transition: str | None = None
    repair_notes: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)


class VisualAnnotation(StrictModel):
    type: Literal["strike", "check", "cross", "underline", "circle_highlight", "stamp", "question", "arrow", "tag", "pencil"] = "circle_highlight"
    target: str = ""
    at_phrase: str = ""
    at_sec: float | None = None
    text: str = ""
    repair_notes: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)


class VisualMascot(StrictModel):
    state: Literal["idle", "point", "shrug", "surprised", "think"] = "idle"
    at_phrase: str = ""
    at_sec: float | None = None


class VisualSFX(StrictModel):
    type: Literal["pop", "whoosh", "click", "chime", "snap"] = "pop"
    at_phrase: str = ""
    at_sec: float | None = None


class VisualScene(StrictModel):
    scene_id: int
    purpose: Literal["hook", "explain", "example", "analysis", "evaluate", "climax", "recap"] = "explain"
    section_title: str = ""
    section_icon: str = "sparkles"
    layout: Literal["center_hero", "split_2", "stack_3", "grid_4", "timeline_h"] = "center_hero"
    camera: SceneCamera = Field(default_factory=SceneCamera)
    elements: list[VisualElement] = Field(default_factory=list)
    annotations: list[VisualAnnotation] = Field(default_factory=list)
    mascot: VisualMascot | None = None
    sfx: list[VisualSFX] = Field(default_factory=list)
    highlight_words: list[str] = Field(default_factory=list)
    repair_notes: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)


class CentralMetaphor(StrictModel):
    name: str = ""
    anchor_element: str = ""
    states_by_scene: dict[str, str] = Field(default_factory=dict)


class VisualPlanResponse(StrictModel):
    theme: Literal["neon_dark", "paper_brand", "whiteboard_sketch"] = "neon_dark"
    central_metaphor: CentralMetaphor = Field(default_factory=CentralMetaphor)
    scenes: list[VisualScene] = Field(default_factory=list)
    repair_notes: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)


def normalize_visual_v3_payload(raw: Any) -> dict[str, Any]:
    """Pre-validation normalization for VisualPlanResponse: strip unknown keys and populate notes."""
    if not isinstance(raw, dict):
        return {}
    data = dict(raw)
    notes: list[str] = []

    allowed_top = set(VisualPlanResponse.model_fields.keys())
    for k in list(data.keys()):
        if k not in allowed_top:
            notes.append(f"[visual_extra, nhóm 3] Bỏ khóa lạ '{k}' ngoài hợp đồng VisualPlanResponse.")
            data.pop(k, None)

    # Theme
    theme = str(data.get("theme") or "neon_dark").strip().lower()
    if theme not in {"neon_dark", "paper_brand", "whiteboard_sketch"}:
        notes.append(f"[theme, nhóm 2] Chủ đề '{theme}' không hợp lệ; dùng neon_dark.")
        theme = "neon_dark"
    data["theme"] = theme

    # Central Metaphor
    meta_raw = data.get("central_metaphor")
    if isinstance(meta_raw, dict):
        meta_dict = dict(meta_raw)
        allowed_meta = set(CentralMetaphor.model_fields.keys())
        for k in list(meta_dict.keys()):
            if k not in allowed_meta:
                meta_dict.pop(k, None)
        meta_dict["name"] = str(meta_dict.get("name") or "").strip()
        meta_dict["anchor_element"] = str(meta_dict.get("anchor_element") or "").strip()
        states = meta_dict.get("states_by_scene")
        meta_dict["states_by_scene"] = {str(k): str(v) for k, v in states.items()} if isinstance(states, dict) else {}
        data["central_metaphor"] = meta_dict
    elif isinstance(meta_raw, str) and meta_raw.strip():
        data["central_metaphor"] = {"name": meta_raw.strip(), "anchor_element": meta_raw.strip(), "states_by_scene": {}}
    else:
        data["central_metaphor"] = {"name": "Hệ thống chịu tải", "anchor_element": "cỗ máy", "states_by_scene": {}}

    # Scenes
    scenes_in = data.get("scenes")
    if not isinstance(scenes_in, list):
        scenes_in = []
    
    cleaned_scenes: list[dict[str, Any]] = []
    allowed_scene = set(VisualScene.model_fields.keys())
    allowed_element = set(VisualElement.model_fields.keys())

    for idx, sc in enumerate(scenes_in):
        if not isinstance(sc, dict):
            continue
        sc_data = dict(sc)
        sc_notes: list[str] = []
        for k in list(sc_data.keys()):
            if k not in allowed_scene:
                sc_notes.append(f"[visual_extra, nhóm 3] Cảnh {idx+1}: bỏ khóa lạ '{k}' ngoài VisualScene.")
                sc_data.pop(k, None)

        try:
            sc_data["scene_id"] = int(sc_data.get("scene_id", idx + 1))
        except (ValueError, TypeError):
            sc_data["scene_id"] = idx + 1

        purpose = str(sc_data.get("purpose") or "explain").strip().lower()
        if purpose not in {"hook", "explain", "example", "analysis", "evaluate", "climax", "recap"}:
            purpose = "explain"
        sc_data["purpose"] = purpose

        sc_data["section_title"] = str(sc_data.get("section_title") or "")[:30].strip()
        sc_data["section_icon"] = str(sc_data.get("section_icon") or "sparkles").strip()

        layout = str(sc_data.get("layout") or "center_hero").strip().lower()
        if layout not in {"center_hero", "split_2", "stack_3", "grid_4", "timeline_h"}:
            layout = "center_hero"
        sc_data["layout"] = layout

        # Camera
        cam = sc_data.get("camera")
        if isinstance(cam, dict):
            cam_data = dict(cam)
            move = str(cam_data.get("move") or cam_data.get("kind") or "push_in").strip().lower()
            if move not in {"push_in", "pull_out", "pan_left", "pan_right"}:
                move = "push_in"
            amount = float(cam_data.get("amount") or 0.04)
            amount = max(0.04, min(0.08, amount))
            sc_data["camera"] = {"kind": move, "amount": amount}
        else:
            sc_data["camera"] = {"kind": "push_in", "amount": 0.04}

        # Elements
        elems_in = sc_data.get("elements")
        cleaned_elements: list[dict[str, Any]] = []
        if isinstance(elems_in, list):
            for e_idx, el in enumerate(elems_in):
                if not isinstance(el, dict):
                    continue
                el_data = dict(el)
                for k in list(el_data.keys()):
                    if k not in allowed_element:
                        sc_notes.append(f"[visual_extra, nhóm 3] Cảnh {idx+1} phần tử {e_idx+1}: bỏ khóa lạ '{k}'.")
                        el_data.pop(k, None)
                el_data["id"] = str(el_data.get("id") or f"e{idx+1}_{e_idx+1}").strip()
                el_data["type"] = str(el_data.get("type") or "stat_number").strip()
                zone = str(el_data.get("zone") or "center").strip().lower()
                if zone not in {"top", "middle", "bottom", "left", "right", "center"}:
                    zone = "center"
                el_data["zone"] = zone
                el_data["content"] = el_data.get("content") if isinstance(el_data.get("content"), dict) else {}
                el_data["evidence"] = str(el_data.get("evidence") or "").strip()
                el_data["no_numbers"] = bool(el_data.get("no_numbers", False))

                # Enter & Exit
                enter = el_data.get("enter")
                if isinstance(enter, dict):
                    anim = str(enter.get("anim") or "pop").strip().lower()
                    if anim not in {"slide_up", "pop", "draw", "fill", "type", "count_up"}:
                        anim = "pop"
                    el_data["enter"] = {"at_phrase": str(enter.get("at_phrase") or "").strip(), "anim": anim, "at_sec": enter.get("at_sec")}
                else:
                    el_data["enter"] = {"at_phrase": "", "anim": "pop", "at_sec": None}

                exit_data = el_data.get("exit")
                if isinstance(exit_data, dict):
                    anim = str(exit_data.get("anim") or "fade").strip().lower()
                    if anim not in {"fade", "slide_down", "pop_out"}:
                        anim = "fade"
                    el_data["exit"] = {"at_phrase": str(exit_data.get("at_phrase") or "scene_end").strip(), "anim": anim, "at_sec": exit_data.get("at_sec")}
                else:
                    el_data["exit"] = {"at_phrase": "scene_end", "anim": "fade", "at_sec": None}

                cleaned_elements.append(el_data)
        sc_data["elements"] = cleaned_elements

        # Annotations
        annots_in = sc_data.get("annotations")
        cleaned_annots: list[dict[str, Any]] = []
        if isinstance(annots_in, list):
            for an in annots_in:
                if not isinstance(an, dict):
                    continue
                an_data = dict(an)
                an_type = str(an_data.get("type") or "circle_highlight").strip().lower()
                if an_type not in {"strike", "check", "cross", "underline", "circle_highlight", "stamp", "question", "arrow", "tag", "pencil"}:
                    an_type = "circle_highlight"
                cleaned_annots.append({
                    "type": an_type,
                    "target": str(an_data.get("target") or "").strip(),
                    "at_phrase": str(an_data.get("at_phrase") or "").strip(),
                    "at_sec": an_data.get("at_sec"),
                    "text": str(an_data.get("text") or "")[:20].strip(),
                })
        sc_data["annotations"] = cleaned_annots

        # Mascot
        mascot_raw = sc_data.get("mascot")
        if isinstance(mascot_raw, dict):
            m_state = str(mascot_raw.get("state") or "idle").strip().lower()
            if m_state not in {"idle", "point", "shrug", "surprised", "think"}:
                m_state = "idle"
            sc_data["mascot"] = {
                "state": m_state,
                "at_phrase": str(mascot_raw.get("at_phrase") or "").strip(),
                "at_sec": mascot_raw.get("at_sec"),
            }
        else:
            sc_data["mascot"] = None

        # SFX
        sfx_in = sc_data.get("sfx")
        cleaned_sfx: list[dict[str, Any]] = []
        if isinstance(sfx_in, list):
            for sf in sfx_in:
                if isinstance(sf, dict):
                    sf_type = str(sf.get("type") or "pop").strip().lower()
                    if sf_type not in {"pop", "whoosh", "click", "chime"}:
                        sf_type = "pop"
                    cleaned_sfx.append({"type": sf_type, "at_phrase": str(sf.get("at_phrase") or "").strip(), "at_sec": sf.get("at_sec")})
        sc_data["sfx"] = cleaned_sfx

        # Highlight words
        hw = sc_data.get("highlight_words")
        sc_data["highlight_words"] = [str(w).strip() for w in hw if str(w).strip()] if isinstance(hw, list) else []

        if sc_notes:
            existing = list(sc_data.get("repair_notes") or [])
            sc_data["repair_notes"] = existing + sc_notes
        cleaned_scenes.append(sc_data)

    data["scenes"] = cleaned_scenes
    if notes:
        existing = list(data.get("repair_notes") or [])
        data["repair_notes"] = existing + notes

    return data
