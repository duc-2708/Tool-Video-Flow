# file: pipeline/assets.py
"""TTS + stock assets, dùng chung CLI/UI, chưa render video."""
import argparse
import logging
import math
from itertools import cycle
from pathlib import Path
from typing import Callable
from config.settings import Settings, get_settings
from pipeline.projects import read_json
from pipeline.stock_assets import MediaDownloader, resolve_stock
from providers.stock_base import StockProvider
from providers.stock_pixabay import PixabayProvider
from providers.stock_pexels import PexelsProvider
from providers.tts_edge import EdgeTTSProvider
from schemas.assets import AssetsManifest, ResolvedEditPlan, SceneAssets
from schemas.edit_plan import EditPlan, Scene, Shot
from utils.cache import cache_key, write_json
from utils.atomic_io import write_text_atomic
from utils.console import configure_console
from utils.diagnostics import Diagnostics
from utils.source_credits import source_credit_lines
from utils.plan_lookup import shot_lookup
from agents.plan_structure import normalize_plan_structure


def assets_diagnostics(settings: Settings, debug: bool = False) -> Diagnostics:
    return Diagnostics(settings.logs_dir, debug=debug, filename="assets_errors.log",
        secrets=[getattr(settings, name + "_api_key").get_secret_value() for name in ("pixabay", "pexels", "gemini", "youtube")])


def stock_providers(settings: Settings, diagnostics: Diagnostics) -> list[StockProvider]:
    result: list[StockProvider] = [PixabayProvider(settings, diagnostics)]
    if settings.pexels_api_key.get_secret_value().strip():
        result.append(PexelsProvider(settings, diagnostics))
    return result


def source_hash(plan: EditPlan) -> str:
    data = plan.model_dump(mode="json")
    # Prompt-only edits do not change narration, timing or stock assets.
    for scene in data["scenes"]:
        for shot in scene["shots"]:
            shot.pop("ai_prompt",None)
    return cache_key(data)


def retime_scene(scene: Scene, duration: float, target_shot_sec: float = 3.) -> Scene:
    if not math.isfinite(duration) or duration < 1.5:
        raise ValueError("Audio cần dài ít nhất 1.5 giây sau khi thêm khoảng lặng.")
    scene=Scene.model_validate(normalize_plan_structure({"scenes":[scene.model_dump(mode="json")]})["scenes"][0])
    minimum, maximum = math.ceil(duration / 4), math.floor(duration / 1.5)
    target_shot_sec = min(4., max(1.5, target_shot_sec))
    count = min(max(len(scene.shots), math.ceil(duration / target_shot_sec), minimum), maximum)
    durations = [round(duration / count, 6)] * count
    durations[-1] = duration - sum(durations[:-1])
    shots = []
    for source, value in zip(cycle(scene.shots), durations):
        data = source.model_dump(mode="json")
        data["duration_sec"] = value
        shots.append(Shot.model_validate(data))
    return Scene.model_validate({**scene.model_dump(mode="json"), "shots": [s.model_dump(mode="json") for s in shots]})


def safe_asset_path(project: Path, relative: str) -> Path:
    if not relative:
        raise ValueError("Đường dẫn asset trống.")
    path = (project / relative).resolve()
    if not path.is_relative_to(project.resolve()) or path.parent == project.resolve() or Path(relative).parts[0] not in {"audio", "clips"}:
        raise ValueError("Đường dẫn asset nằm ngoài thư mục audio/clips của project.")
    return path


def load_assets(plan_path: Path) -> tuple[EditPlan, ResolvedEditPlan, AssetsManifest]:
    original = EditPlan.model_validate(read_json(plan_path))
    resolved = ResolvedEditPlan.model_validate(read_json(plan_path.parent / "edit_plan.resolved.json"))
    manifest = AssetsManifest.model_validate(read_json(plan_path.parent / "assets.json"))
    if source_hash(original) != manifest.source_plan_hash or resolved.source_plan_hash != manifest.source_plan_hash:
        raise ValueError("Edit Plan gốc đã đổi; hãy tạo lại Assets để tránh dùng audio/clip cũ.")
    if cache_key(resolved.model_dump(mode="json")) != manifest.resolved_plan_hash:
        raise ValueError("Resolved plan không khớp manifest; hãy tạo lại Assets.")
    return original, resolved, manifest


def write_credits(project: Path, manifest: AssetsManifest, diagnostics: Diagnostics) -> None:
    lines = ["CREDITS — video_ai_tool", "Chỉ liệt kê tài nguyên đang được dùng trong assets.json.", ""]
    for scene in manifest.scenes:
        if scene.audio_path:
            lines.append(f"Cảnh {scene.scene_id}: giọng đọc Microsoft Edge TTS, nội dung theo narration của project.")
        for shot in scene.shots:
            location = f"Cảnh {scene.scene_id} / shot {shot.shot_id}"
            if shot.provider == "generated":
                lines.append(f"{location}: nền màu/chữ tạo bằng code, không dùng media bên ngoài.")
            else:
                lines.extend([f"{location}: {shot.provider.title()} — asset {shot.asset_id}",
                              f"Tác giả: {shot.author}", f"Nguồn: {shot.source_url}", f"File: {shot.path}"])
    lines.extend(["", "License Pixabay: https://pixabay.com/service/license-summary/",
                  "License Pexels: https://www.pexels.com/license/"])
    lines.extend(source_credit_lines(project))
    write_text_atomic(project / "credits.txt", diagnostics.redact("\n".join(lines) + "\n"))


def persist(project: Path, resolved: ResolvedEditPlan, manifest: AssetsManifest, diagnostics: Diagnostics) -> Path:
    manifest.resolved_plan_hash = cache_key(resolved.model_dump(mode="json"))
    write_json(project / "edit_plan.resolved.json", resolved.model_dump(mode="json"))
    write_json(project / "assets.json", manifest.model_dump(mode="json"))
    write_credits(project, manifest, diagnostics)
    return project / "assets.json"


def run_assets(plan_path: Path, settings: Settings, *, progress: Callable[[int, int, str], None] | None = None,
               debug: bool = False, tts=None, providers: list[StockProvider] | None = None,
               downloader: MediaDownloader | None = None) -> Path:
    diagnostics = assets_diagnostics(settings, debug)
    try:
        original = EditPlan.model_validate(read_json(plan_path))
        project = plan_path.parent
        fingerprint = source_hash(original)
        settings.ensure_directories()
        tts = tts or EdgeTTSProvider(settings, diagnostics)
        providers = stock_providers(settings, diagnostics) if providers is None else providers
        downloader = downloader or MediaDownloader(settings, diagnostics)
        warnings: list[str] = []
        if not settings.pixabay_api_key.get_secret_value().strip() and providers:
            warnings.append("Chưa có PIXABAY_API_KEY; sẽ dùng stock tùy chọn hoặc nền màu khi không tìm được clip.")
        # Giữ query thay riêng shot khi chạy lại cùng Edit Plan.
        previous_queries = {}
        try:
            old = AssetsManifest.model_validate(read_json(project / "assets.json"))
            if old.source_plan_hash == fingerprint:
                previous_queries = {(s.scene_id, a.shot_id): a.query for s in old.scenes for a in s.shots}
        except (OSError, ValueError):
            pass
        scene_plans, scene_assets = [], []
        for index, scene in enumerate(original.scenes):
            if progress:
                progress(index, len(original.scenes), f"Cảnh {scene.id}: đang tạo giọng và chuẩn bị b-roll…")
            audio_path = project / "audio" / f"scene_{scene.id}.mp3"
            duration, audio_error = None, None
            resolved_scene = scene.model_copy(deep=True)
            try:
                duration = tts.synthesize(scene.narration, original.voice, audio_path)
                resolved_scene = retime_scene(scene, duration, original.style_profile.shot_seconds.mean if original.style_profile else 3.)
                if len(resolved_scene.shots) != len(scene.shots):
                    warnings.append(f"Cảnh {scene.id}: số shot đổi từ {len(scene.shots)} thành {len(resolved_scene.shots)} theo audio thật.")
                if scene.role == "hook" and duration > 3:
                    warnings.append(f"Hook có audio thật {duration:.2f}s, vượt 3s; cần rút lời đọc nếu muốn hook ngắn hơn.")
            except Exception as error:
                diagnostics.record_exception(error, f"Assets TTS cảnh {scene.id}")
                audio_error = diagnostics.redact(f"{type(error).__name__}: {error}")[:1500]
                warnings.append(f"Cảnh {scene.id}: chưa có audio hợp lệ; giữ thời gian kế hoạch cũ, cần chạy lại Assets.")
                duration = None
            shot_assets, updated_shots = [], []
            for shot_id, shot in enumerate(resolved_scene.shots, 1):
                override = previous_queries.get((scene.id, shot_id))
                if override:
                    shot = Shot.model_validate({**shot.model_dump(mode="json"), "query": override})
                asset = resolve_stock(shot, scene.id, shot_id, scene.narration, original.format,
                                      project, providers, downloader, diagnostics)
                shot.type = {"video": "stock_video", "image": "stock_image", "color": "text_card"}[asset.media_type]
                if asset.media_type == "color":
                    shot.text_overlay = shot.text_overlay or scene.narration
                shot_assets.append(asset)
                updated_shots.append(shot)
            resolved_scene.shots = updated_shots
            scene_plans.append(resolved_scene.model_dump(mode="json"))
            scene_assets.append(SceneAssets(scene_id=scene.id,
                audio_path=audio_path.relative_to(project).as_posix() if duration else None,
                audio_duration_sec=duration, audio_error=audio_error, shots=shot_assets))
            if progress:
                progress(index + 1, len(original.scenes), f"Cảnh {scene.id}: đã chuẩn bị xong" + (" (audio cần thử lại)" if audio_error else ""))
        data = {**original.model_dump(mode="json"), "scenes": scene_plans,
                "source_plan_hash": fingerprint, "warnings": warnings, "timing_basis": "audio"}
        resolved = ResolvedEditPlan.model_validate(data)
        if original.target_duration_sec:
            try:
                resolved.validate_target_duration(original.target_duration_sec)
            except ValueError:
                warnings.append(f"Tổng thời lượng theo audio {resolved.duration_sec:.2f}s khác yêu cầu {original.target_duration_sec:.2f}s quá 10%; chưa tự đổi tốc độ giọng.")
        resolved.warnings = list(dict.fromkeys(warnings))
        manifest = AssetsManifest(source_plan_hash=fingerprint, resolved_plan_hash=cache_key(resolved.model_dump(mode="json")),
            status="partial" if any(s.audio_error for s in scene_assets) else "complete",
            scenes=scene_assets, warnings=resolved.warnings)
        return persist(project, resolved, manifest, diagnostics)
    except Exception as error:
        diagnostics.record_exception(error, "Assets pipeline failed")
        raise


def refresh_shot(plan_path: Path, settings: Settings, scene_id: int, shot_id: int, query: str,
                 *, providers: list[StockProvider] | None = None, downloader: MediaDownloader | None = None) -> Path:
    diagnostics = assets_diagnostics(settings)
    try:
        original, resolved, manifest = load_assets(plan_path)
        scene = next((s for s in resolved.scenes if s.id == scene_id), None)
        assets_scene = next((s for s in manifest.scenes if s.scene_id == scene_id), None)
        previous = shot_lookup(resolved).get((scene_id, shot_id))
        current = next((s for s in assets_scene.shots if s.shot_id == shot_id), None) if assets_scene else None
        if previous is None or current is None:
            raise ValueError(f"Không tìm thấy cảnh {scene_id} / shot {shot_id} trong plan hoặc manifest; hãy tạo lại Assets.")
        shot = Shot.model_validate({**previous.model_dump(mode="json"), "query": query, "type": "stock_video"})
        providers = stock_providers(settings, diagnostics) if providers is None else providers
        replacement = resolve_stock(shot, scene_id, shot_id, scene.narration, original.format, plan_path.parent,
            providers, downloader or MediaDownloader(settings, diagnostics), diagnostics,
            exclude=(current.provider, current.asset_id) if query == current.query and current.asset_id else None)
        shot.type = {"video": "stock_video", "image": "stock_image", "color": "text_card"}[replacement.media_type]
        if replacement.media_type == "color":
            shot.text_overlay = shot.text_overlay or scene.narration
        scene.shots = [shot if item is previous else item for item in scene.shots]
        assets_scene.shots = [replacement if item.shot_id == shot_id else item for item in assets_scene.shots]
        return persist(plan_path.parent, resolved, manifest, diagnostics)
    except Exception as error:
        diagnostics.record_exception(error, f"Assets tìm lại cảnh {scene_id} shot {shot_id}")
        raise


def main() -> int:
    configure_console()
    logging.getLogger().setLevel(logging.CRITICAL)
    parser = argparse.ArgumentParser(description="Tạo Assets từ Edit Plan (chưa render)")
    parser.add_argument("edit_plan", type=Path)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    diagnostics = Diagnostics(Path(__file__).resolve().parents[1] / "logs", debug=args.debug, filename="assets_errors.log")
    try:
        path = run_assets(args.edit_plan, get_settings(), debug=args.debug,
            progress=lambda done, total, text: print(f"[{done}/{total}] {text}"))
        manifest = AssetsManifest.model_validate(read_json(path))
    except Exception as error:
        diagnostics.record_exception(error, "Assets CLI failed")
        print("Không tạo được Assets: " + diagnostics.redact(str(error))[:1500])
        return 1
    fallbacks = sum(a.fallback for s in manifest.scenes for a in s.shots)
    print(f"Đã lưu: {path}; trạng thái={manifest.status}; shot fallback={fallbacks}.")
    print("Kế hoạch thời gian: edit_plan.resolved.json; nguồn: credits.txt. Chưa render video.")
    return 0 if manifest.status == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
