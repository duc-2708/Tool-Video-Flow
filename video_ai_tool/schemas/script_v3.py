"""Schema and pre-validation normalizer for Script Writer v3 (Prompt A)."""
from typing import Literal, Any, get_args, get_origin
from pydantic import Field
from schemas.base import StrictModel


class ScriptV3Sentence(StrictModel):
    text: str
    type: Literal["event", "explain", "opinion", "cta"] = "explain"
    fact_ids: list[int] = Field(default_factory=list)
    repair_notes: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)


class ScriptV3Scene(StrictModel):
    scene_id: int
    purpose: Literal["hook", "explain", "example", "analysis", "evaluate", "climax", "cta"] = "explain"
    sentences: list[ScriptV3Sentence] = Field(default_factory=list)
    visual_hint: str = ""
    repair_notes: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)


class ScriptV3Response(StrictModel):
    title: str = ""
    central_metaphor: str = ""
    scenes: list[ScriptV3Scene] = Field(default_factory=list)
    repair_notes: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)


PURPOSE_SYNONYMS = {
    "hook": "hook",
    "explain": "explain",
    "explanation": "explain",
    "body": "explain",
    "example": "example",
    "analysis": "analysis",
    "evaluate": "evaluate",
    "evaluation": "evaluate",
    "climax": "climax",
    "cta": "cta",
    "recap": "cta",
    "conclusion": "cta",
    "outro": "cta",
}

TYPE_SYNONYMS = {
    "event": "event",
    "explain": "explain",
    "explanation": "explain",
    "opinion": "opinion",
    "cta": "cta",
}


def normalize_script_v3_payload(payload: Any) -> dict[str, Any]:
    """Pre-validation normalization: strip extra keys, note group 3 warnings, fill safe defaults."""
    if not isinstance(payload, dict):
        return {}
    data = dict(payload)
    notes: list[str] = []

    # Strip unknown top-level keys
    allowed_top = set(ScriptV3Response.model_fields.keys())
    for k in list(data.keys()):
        if k not in allowed_top:
            notes.append(f"[script_extra, nhóm 3] Bỏ khóa lạ '{k}' ngoài hợp đồng ScriptV3Response; không dùng giá trị đó.")
            data.pop(k, None)

    # Title & metaphor
    data["title"] = str(data.get("title") or "").strip()
    data["central_metaphor"] = str(data.get("central_metaphor") or "").strip()

    # Scenes
    scenes_in = data.get("scenes")
    if not isinstance(scenes_in, list):
        scenes_in = []
    
    allowed_scene = set(ScriptV3Scene.model_fields.keys())
    allowed_sentence = set(ScriptV3Sentence.model_fields.keys())
    cleaned_scenes: list[dict[str, Any]] = []

    for idx, sc in enumerate(scenes_in):
        if not isinstance(sc, dict):
            continue
        sc_data = dict(sc)
        sc_notes: list[str] = []
        for k in list(sc_data.keys()):
            if k not in allowed_scene:
                sc_notes.append(f"[script_extra, nhóm 3] Cảnh {idx+1}: bỏ khóa lạ '{k}' ngoài hợp đồng ScriptV3Scene.")
                sc_data.pop(k, None)
        
        # scene_id
        try:
            sc_data["scene_id"] = int(sc_data.get("scene_id", idx + 1))
        except (ValueError, TypeError):
            sc_data["scene_id"] = idx + 1

        # purpose
        raw_purpose = str(sc_data.get("purpose") or "explain").strip().lower()
        sc_data["purpose"] = PURPOSE_SYNONYMS.get(raw_purpose, "explain")
        sc_data["visual_hint"] = str(sc_data.get("visual_hint") or "").strip()

        # sentences
        sents_in = sc_data.get("sentences")
        if not isinstance(sents_in, list):
            sents_in = []
        cleaned_sentences: list[dict[str, Any]] = []

        for s_idx, st in enumerate(sents_in):
            if not isinstance(st, dict):
                if isinstance(st, str) and st.strip():
                    st = {"text": st.strip(), "type": "explain", "fact_ids": []}
                else:
                    continue
            st_data = dict(st)
            for k in list(st_data.keys()):
                if k not in allowed_sentence:
                    sc_notes.append(f"[script_extra, nhóm 3] Cảnh {idx+1} câu {s_idx+1}: bỏ khóa lạ '{k}'.")
                    st_data.pop(k, None)

            st_data["text"] = str(st_data.get("text") or "").strip()
            raw_type = str(st_data.get("type") or "explain").strip().lower()
            st_data["type"] = TYPE_SYNONYMS.get(raw_type, "explain")

            raw_facts = st_data.get("fact_ids")
            if isinstance(raw_facts, list):
                valid_facts = []
                for f in raw_facts:
                    try:
                        valid_facts.append(int(f))
                    except (ValueError, TypeError):
                        pass
                st_data["fact_ids"] = valid_facts
            else:
                st_data["fact_ids"] = []

            if st_data["text"]:
                cleaned_sentences.append(st_data)

        sc_data["sentences"] = cleaned_sentences
        if sc_notes:
            existing = list(sc_data.get("repair_notes") or [])
            sc_data["repair_notes"] = existing + sc_notes
        cleaned_scenes.append(sc_data)

    data["scenes"] = cleaned_scenes
    if notes:
        existing = list(data.get("repair_notes") or [])
        data["repair_notes"] = existing + notes

    return data
