"""Stage Engine: Sân khấu + Diễn viên + Kịch bản chuyển động (Giai đoạn 5a)."""
from editor.stage.schema import StageScript, ActorDef, ActionDef, SceneDef, HUDDef, ThemeDef, RecapDef
from editor.stage.compiler import compile_stage_script, build_stage_html
from editor.stage.renderer import render_stage_script

__all__ = [
    "StageScript",
    "ActorDef",
    "ActionDef",
    "SceneDef",
    "HUDDef",
    "ThemeDef",
    "RecapDef",
    "compile_stage_script",
    "build_stage_html",
    "render_stage_script"
]
