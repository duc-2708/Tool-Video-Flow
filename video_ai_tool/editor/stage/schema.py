"""Pydantic schemas for Stage Engine DSL (Sân khấu + Diễn viên + Kịch bản chuyển động)."""
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


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
    type: str  # laptop, vps_server, data_packet, connection_path, progress_tracker, etc.
    pos: Union[List[float], str] = Field(default_factory=lambda: [0.0, 0.0, 0.0])  # [x, y, z] or zone name
    state: str = "default"  # laptop: closed/open/typing/glow; vps: off/on/busy; file: idle/flying
    label: str = ""
    sublabel: str = ""
    scale: float = 1.0
    opacity: float = 1.0
    visible: bool = True
    params: Dict[str, Any] = Field(default_factory=dict)


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
    y: float = 960.0
    zoom: float = 1.0
    tilt: float = 0.0
    duration: float = 0.8
    easing: str = "easeInOutQuad"


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
    theme: ThemeDef = Field(default_factory=ThemeDef)
    hud: HUDDef = Field(default_factory=HUDDef)
    actors: List[ActorDef] = Field(default_factory=list)
    scenes: List[SceneDef] = Field(default_factory=list)
    recap: Optional[RecapDef] = None

    @classmethod
    def export_json_schema(cls) -> Dict[str, Any]:
        """Export JSON Schema for documentation and LLM Prompt integration."""
        return cls.model_json_schema()
