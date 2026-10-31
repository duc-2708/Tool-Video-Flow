"""Pydantic schemas for Visual Bible (Kế hoạch hình ảnh tổng cho toàn bộ video).
Giai đoạn 8-W2a: Visual Bible định nghĩa thế giới isometric, vật thể xuyên suốt,
tiến độ ẩn dụ và cấu trúc chương trước khi phân rã shot motion.
"""
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field

WorldKind = Literal[
    "secure_building",
    "data_pipeline",
    "workshop",
    "city_road",
    "courtroom",
    "lab",
    "generic_stage",
]

ProgressMetaphorType = Literal["none", "glass_fill", "step_bar", "stack_up"]

ALLOWED_WORLD_KINDS = {
    "secure_building",
    "data_pipeline",
    "workshop",
    "city_road",
    "courtroom",
    "lab",
    "generic_stage",
}

ALLOWED_ACTOR_TYPES = {
    "laptop",
    "vps_server",
    "docker_container",
    "container_box",
    "cloud",
    "code_repo",
    "git_repo",
    "terminal_window",
    "browser_window",
    "lock_shield",
    "user_figure",
    "datacenter",
    "note_board",
}


class WorldDef(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    kind: WorldKind = "generic_stage"
    reason: str = Field(..., description="Lý do thế giới này hợp chủ đề (1 câu)")
    zones: List[str] = Field(default_factory=list, description="Danh sách các zone/khu vực trong thế giới")


class PersistentActorDef(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    type: str = Field(..., description="Loại actor từ catalog Stage DSL")
    role: str = Field(..., description="Vai trò hoặc đại diện cho khái niệm nào trong video")
    states: List[str] = Field(default_factory=list, description="Các trạng thái hiển thị có thể có")


class ChapterDef(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: Union[str, int]
    title: str = Field(..., description="Tiêu đề chương (tối đa 5 từ)")
    scene_ids: List[Union[str, int]] = Field(default_factory=list, description="Danh sách id các cảnh thuộc chương")
    kicker: str = Field(..., description="Kicker định dạng 'PHẦN i/N'")


class StructureDef(BaseModel):
    model_config = ConfigDict(extra="ignore")
    chapters: List[ChapterDef] = Field(default_factory=list, description="Danh sách các chương")


class ProgressMetaphorDef(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: ProgressMetaphorType = "none"
    items: List[str] = Field(default_factory=list, description="Các mục/cột mốc tiến độ lấy từ nội dung")


class ConceptDef(BaseModel):
    model_config = ConfigDict(extra="ignore")
    term: str = Field(..., description="Khái niệm / thuật ngữ")
    scene_id: Union[str, int]
    sentence_index: int = 1
    world_zone: str = "main_zone"
    actor_id: Optional[str] = None
    evidence_sentence: str = Field(..., description="Câu trong lời đọc/brief chứa khái niệm này")


class PaletteDef(BaseModel):
    model_config = ConfigDict(extra="ignore")
    top: str = "#101b30"
    bottom: str = "#080c17"
    card: str = "#16263b"
    foreground: str = "#f4f7ff"
    accent: str = "#ffd052"
    secondary: str = "#61d7c3"


class VisualBible(BaseModel):
    model_config = ConfigDict(extra="ignore")
    theme_name: str = "neon_dark"
    palette: Dict[str, str] = Field(default_factory=dict, description="Bảng màu chính từ theme")
    worlds: List[WorldDef] = Field(default_factory=list, max_length=2, description="Tối đa 2 thế giới")
    persistent_actors: List[PersistentActorDef] = Field(default_factory=list, max_length=3, description="Tối đa 3 vật thể xuyên suốt")
    structure: StructureDef = Field(default_factory=StructureDef, description="Cấu trúc phân đoạn chương")
    progress_metaphor: ProgressMetaphorDef = Field(default_factory=ProgressMetaphorDef, description="Ẩn dụ tiến độ xuyên suốt")
    concepts: List[ConceptDef] = Field(default_factory=list, description="Ánh xạ các khái niệm vào world zone và actor")
    numbers_allowed: List[Union[float, int, str]] = Field(default_factory=list, description="Các số liệu xuất hiện trong lời đọc/brief")
    notes: List[str] = Field(default_factory=list, description="Ghi chú kỹ thuật hoặc giải trình của Visual Bible")


class VisualBibleStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")
    llm_ok: bool = True
    fallback_used: bool = False
    reason: str = ""
    timestamp: str = ""
