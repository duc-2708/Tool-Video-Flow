"""Pydantic schemas for Stage Engine DSL (Sân khấu + Diễn viên + Kịch bản chuyển động)."""
import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator

_CATALOG_PATH = Path(__file__).resolve().parent / "catalog.json"

def get_stage_catalog() -> Dict[str, Any]:
    if _CATALOG_PATH.is_file():
        try:
            return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"actors": {}, "worlds": {}}

_CATALOG = get_stage_catalog()
ALLOWED_STAGE_ACTORS = set(_CATALOG.get("actors", {}).keys())
# Utility structural pseudo-actors allowed in legacy scripts (e.g. connections, data packets, road morph)
STRUCTURAL_ACTOR_TYPES = {"connection_path", "data_packet", "road"}

GROUP_FALLBACKS = {
    "infra": "vps_server",
    "device": "laptop",
    "security": "lock_shield",
    "legal": "document_paper",
    "data": "database_cylinder",
    "character": "mascot",
    "ui": "note_board"
}

def find_nearest_actor_type(invalid_type: str) -> str:
    """Find nearest valid actor type by name similarity or group fallback."""
    lowered = invalid_type.lower()
    for valid_type in ALLOWED_STAGE_ACTORS:
        if valid_type in lowered or lowered in valid_type:
            return valid_type
    if "server" in lowered or "host" in lowered or "cloud" in lowered:
        return "vps_server"
    if "pc" in lowered or "computer" in lowered or "screen" in lowered:
        return "laptop"
    if "lock" in lowered or "safe" in lowered or "protect" in lowered or "shield" in lowered:
        return "lock_shield"
    if "doc" in lowered or "file" in lowered or "law" in lowered or "court" in lowered:
        return "document_paper"
    if "db" in lowered or "data" in lowered or "store" in lowered:
        return "database_cylinder"
    if "bot" in lowered or "robot" in lowered or "assistant" in lowered or "char" in lowered:
        return "mascot"
    return "note_board"


class ThemeDef(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = "neon_purple"
    primary: str = "#9d4edd"      # Vibrant neon purple
    secondary: str = "#00f5d4"    # Neon cyan / teal
    accent: str = "#f72585"       # Electric pink / magenta
    bg: str = "#09041a"           # Deep dark space purple
    grid: str = "rgba(157, 78, 221, 0.22)"
    text: str = "#ffffff"
    glow: str = "rgba(0, 245, 212, 0.5)"


class HUDDef(BaseModel):
    model_config = ConfigDict(extra="ignore")
    brand: str = "TECH EXPLAINER"
    steps: List[str] = Field(default_factory=lambda: ["Bước 1", "Bước 2", "Bước 3", "Bước 4", "Bước 5"])
    active_step: int = 0
    completed_steps: List[int] = Field(default_factory=list)
    tracker_style: Literal["stations", "road"] = "stations"
    footer_note: str = "hình mô phỏng"
    title: str = ""
    subtitle: str = ""


class ActorDef(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    type: str  # Validated against catalog.json
    pos: Union[List[float], str] = Field(default_factory=lambda: [0.0, 0.0, 0.0])  # [x, y, z] or zone name
    state: str = "default"  # laptop: closed/open/typing/glow; vps: off/on/busy; file: idle/flying
    label: str = ""
    sublabel: str = ""
    scale: float = 1.0
    opacity: float = 1.0
    visible: bool = True
    params: Dict[str, Any] = Field(default_factory=dict)
    review_notes: List[str] = Field(default_factory=list)

    @field_validator("type", mode="before")
    @classmethod
    def validate_actor_type(cls, value: Any, info) -> str:
        s_val = str(value).strip()
        all_allowed = ALLOWED_STAGE_ACTORS.union(STRUCTURAL_ACTOR_TYPES)
        if s_val not in all_allowed:
            nearest = find_nearest_actor_type(s_val)
            return nearest
        return s_val

    def model_post_init(self, __context: Any) -> None:
        all_allowed = ALLOWED_STAGE_ACTORS.union(STRUCTURAL_ACTOR_TYPES)
        # Check if type had to be mapped or healed
        orig_val = getattr(self, "_orig_type", None)
        if orig_val and orig_val not in all_allowed:
            self.review_notes.append(f"Actor {self.id}: loại '{orig_val}' không hợp lệ, tự thay bằng '{self.type}'.")


class ActionDef(BaseModel):
    model_config = ConfigDict(extra="ignore")
    at_phrase: Optional[str] = None
    at_sec: float = 0.0
    verb: str  # enter, exit, move_to, set_state, connect, send_packet, type, check, open, close, highlight, focus_camera, label
    target: Union[str, List[str]]
    params: Dict[str, Any] = Field(default_factory=dict)
    duration: float = 0.5
    easing: str = "easeInOutQuad"


class CameraDef(BaseModel):
    model_config = ConfigDict(extra="ignore")
    x: float = 540.0
    y: float = 785.0
    zoom: float = 1.0
    tilt: float = 0.0
    duration: float = 0.8
    easing: str = "easeInOutQuad"

    def clamp_zoom(self) -> "CameraDef":
        if self.zoom > 1.25:
            self.zoom = 1.25
        return self


class SceneDef(BaseModel):
    model_config = ConfigDict(extra="ignore")
    scene_id: Union[str, int]
    step_index: int = 0
    title: str = ""
    duration_sec: float = 5.0
    narration: Optional[str] = None
    camera: Optional[CameraDef] = None
    actions: List[ActionDef] = Field(default_factory=list)


class RecapDef(BaseModel):
    model_config = ConfigDict(extra="ignore")
    morph_tracker_to: Optional[Literal["road"]] = "road"
    recap_duration: float = 4.0


class StageScript(BaseModel):
    model_config = ConfigDict(extra="ignore")
    world: str = "generic_stage"
    theme: ThemeDef = Field(default_factory=ThemeDef)
    hud: HUDDef = Field(default_factory=HUDDef)
    actors: List[ActorDef] = Field(default_factory=list)
    scenes: List[SceneDef] = Field(default_factory=list)
    recap: Optional[RecapDef] = None

    @classmethod
    def export_json_schema(cls) -> Dict[str, Any]:
        """Export JSON Schema for documentation and LLM Prompt integration."""
        return cls.model_json_schema()
