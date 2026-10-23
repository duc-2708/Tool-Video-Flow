"""Read-only, sample-accurate timeline shared by CLI and web UI."""
from dataclasses import dataclass
from pathlib import Path
from schemas.assets import AssetsManifest, ResolvedEditPlan
from schemas.edit_plan import Scene,Shot
from utils.cache import cache_key
from utils.media import measured_audio_duration


def confined(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Đường dẫn media vượt khỏi thư mục được phép.")
    return path


@dataclass
class TimelineShot:
    scene_id: int
    shot_id: int
    start: float
    duration: float
    spec: Shot
    path: Path | None
    fallback: bool


@dataclass
class TimelineScene:
    spec: Scene
    start: float
    duration: float
    audio: Path
    shots: list[TimelineShot]
    audio_silent: bool = False


@dataclass
class Timeline:
    plan: ResolvedEditPlan
    project: Path
    scenes: list[TimelineScene]
    duration: float
    warnings: list[str]


def build_timeline(plan_path: Path) -> Timeline:
    plan_path = Path(plan_path).resolve()
    project = plan_path.parent
    plan = ResolvedEditPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    manifest_path = project / "assets.json"
    manifest = AssetsManifest.model_validate_json(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    if manifest and (manifest.resolved_plan_hash != cache_key(plan.model_dump(mode="json")) or manifest.source_plan_hash != plan.source_plan_hash):
        raise ValueError("Assets không khớp resolved plan. Hãy chạy lại Giai đoạn Assets.")
    records = {s.scene_id: s for s in manifest.scenes} if manifest else {}
    scenes, warnings, clock = [], list(plan.warnings), 0.0
    for scene in plan.scenes:
        for folder in ("audio","clips"):
            confined(project,folder)
        record = records.get(scene.id)
        if manifest and record is None:
            raise ValueError(f"Thiếu bản ghi Assets cảnh {scene.id}. Hãy chạy lại trang Assets.")
        relative = record.audio_path if record else f"audio/scene_{scene.id}.mp3"
        if not relative or Path(relative).parts[0] != "audio":
            raise ValueError(f"Thiếu audio cảnh {scene.id}. Chạy lại: python -m pipeline.assets {project / 'edit_plan.json'}")
        audio = confined(project / "audio", str(Path(relative).relative_to("audio")))
        if not audio.is_file():
            raise ValueError(f"Thiếu audio cảnh {scene.id}: {audio.name}. Hãy chạy lại trang Assets trước khi render.")
        duration = measured_audio_duration(audio)
        assets = {s.shot_id: s for s in record.shots} if record else {}
        shots, local = [], 0.0
        for index, shot in enumerate(scene.shots, 1):
            asset = assets.get(index)
            path = None
            if asset:
                if Path(asset.path).parts[0] != "clips":
                    raise ValueError("Clip phải nằm trong clips/ của project.")
                path = confined(project / "clips", str(Path(asset.path).relative_to("clips")))
            elif not manifest:
                candidates = sorted((project/"clips").glob(f"scene_{scene.id}_shot_{index}_*"))
                candidates = [p for p in candidates if p.suffix.lower() in {".mp4",".mov",".webm",".jpg",".jpeg",".png",".webp"}]
                if candidates:
                    path = confined(project/"clips",candidates[0].name)
            fallback = path is None or not path.is_file() or (asset and asset.media_type == "color") or (path and "_fallback_" in path.name)
            if fallback and not (shot.visual and shot.visual.template!="stock"):
                warnings.append(f"Cảnh {scene.id}, shot {index}: dùng nền màu và chữ.")
            length = duration-local if index == len(scene.shots) else duration*shot.duration_sec/scene.duration_sec
            shots.append(TimelineShot(scene.id,index,clock+local,length,shot,path,bool(fallback)))
            local += length
        scenes.append(TimelineScene(scene,clock,duration,audio,shots,bool(record and record.audio_silent)))
        clock += duration
    return Timeline(plan,project,scenes,clock,warnings)
