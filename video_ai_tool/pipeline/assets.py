# file: pipeline/assets.py
"""TTS + stock assets, dùng chung CLI/UI, chưa render video."""
import argparse
import logging
import math
import re
from itertools import cycle
from functools import wraps
from pathlib import Path
from typing import Callable
from config.settings import Settings, get_settings
from pipeline.projects import read_json
from pipeline.stock_assets import MediaDownloader, resolve_stock
from providers.stock_base import StockProvider
from providers.stock_pixabay import PixabayProvider
from providers.stock_pexels import PexelsProvider
from providers.tts_edge import EdgeTTSProvider,TTSError,create_silence,audio_metadata_path,audio_duration
from providers.tts_text import clean_tts_text,has_speech
from schemas.assets import AssetsManifest, ResolvedEditPlan, SceneAssets
from schemas.edit_plan import EditPlan, Scene, Shot
from utils.cache import cache_key, write_json
from utils.atomic_io import write_text_atomic,write_json_atomic,path_lock
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
    lower=2.5 if scene.sentences else 1.5
    minimum, maximum = math.ceil((duration-1e-7) / 4), math.floor((duration+1e-7) / lower)
    if minimum>maximum: raise ValueError("Audio v2 cần thêm khoảng nghỉ để chia shot 2.5–4s; chạy lại audio cảnh này.")
    target_shot_sec = min(4., max(lower, target_shot_sec))
    count = min(max(len(scene.shots), math.ceil(duration / target_shot_sec), minimum), maximum)
    durations = [round(duration / count, 6)] * count
    durations[-1] = duration - sum(durations[:-1])
    shots = []
    for source, value in zip(cycle(scene.shots), durations):
        data = source.model_dump(mode="json")
        data["duration_sec"] = value
        data["planning_duration"]=False
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
        if scene.audio_silent:
            lines.append(f"Cảnh {scene.scene_id}: audio có đoạn im lặng do TTS lỗi; caption theo kịch bản, không phải giọng đọc.")
        elif scene.audio_path:
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


def persist(project: Path, resolved: ResolvedEditPlan, manifest: AssetsManifest, diagnostics: Diagnostics,*,motion_enabled=False) -> Path:
    if motion_enabled:
        from agents.motion_beats import resolved_beats
        resolved_beats(resolved,manifest,project)
    manifest.resolved_plan_hash = cache_key(resolved.model_dump(mode="json"))
    write_json(project / "edit_plan.resolved.json", resolved.model_dump(mode="json"))
    write_json(project / "assets.json", manifest.model_dump(mode="json"))
    write_credits(project, manifest, diagnostics)
    # Standalone Assets and UI repair also publish prominent, current warnings.
    report=project/"report.md"
    previous=report.read_text(encoding="utf-8") if report.exists() else "# Báo cáo Assets\n"
    previous=re.sub(r"\n?<!-- TTS_WARNINGS_BEGIN -->.*?<!-- TTS_WARNINGS_END -->\n?","\n",previous,flags=re.S)
    messages=list(dict.fromkeys(w for scene in manifest.scenes for w in scene.audio_warnings))
    section="\n<!-- TTS_WARNINGS_BEGIN -->\n## Cảnh báo giọng đọc\n"+"\n".join("- **"+w+"**" for w in messages)+"\n<!-- TTS_WARNINGS_END -->\n" if messages else ""
    write_text_atomic(report,diagnostics.redact(previous.rstrip()+"\n"+section))
    return project / "assets.json"


def protected_tts_names(project):
    if not (project/"brief.json").is_file(): return []
    from schemas.research_brief import ResearchBrief
    from agents.director_sources import number_names
    return number_names(ResearchBrief.model_validate(read_json(project/"brief.json")))


def scene_audio(scene,voice,path,settings,diagnostics,tts,protected_names):
    """One explicit audio outcome, including degraded but playable silence."""
    from agents.vietnamese_tts import tts_text
    clean=tts_text(clean_tts_text(scene.narration),protected_names=protected_names)
    try:
        if not has_speech(clean):
            tts=EdgeTTSProvider(settings,diagnostics)  # Offline silence path, no request.
        if isinstance(tts,EdgeTTSProvider):
            duration=tts.synthesize(clean,voice,path,scene_id=scene.id,duration_sec=scene.duration_sec)
            meta=read_json(audio_metadata_path(path))
        else:
            duration=tts.synthesize(clean,voice,path)
            meta={"audio_silent":False,"audio_error":None,"voice_used":voice,"warnings":[]}
            write_json_atomic(audio_metadata_path(path),meta)
        if scene.sentences:
            count=max(1,math.ceil((duration-1e-7)/4))
            target=max(duration,count*2.5)
            if target>duration+1e-6:
                from utils.media import pad_audio_to
                old_duration=duration;duration=pad_audio_to(path,target,settings.request_timeout_sec)
                meta["warnings"].append(f"Cảnh {scene.id}: thêm {duration-old_duration:.2f}s khoảng nghỉ để shot Explainer nằm trong 2.5–4s, giữ toàn bộ lời đọc.")
                write_json_atomic(audio_metadata_path(path),meta)
        from utils.word_timing import read_words,save_words,timing_source,align_words
        timing=path.with_suffix(".words.json")
        observed=read_words(timing);source=timing_source(timing)
        _,method=align_words(scene.narration,duration,observed)
        save_words(timing,scene.narration,duration,observed,source=source if source!="word_boundary" else method)
        return duration,meta
    except Exception as error:
        diagnostics.record_exception(error,f"TTS lỗi ở cảnh {scene.id}; voice={voice}; attempt=provider; text_length={len(clean)}; cleaned_text={clean[:200]!r}")
        message=diagnostics.redact(f"TTS lỗi ở cảnh {scene.id}: {type(error).__name__}: {error}")[:1500]
        try:
            duration=create_silence(path,max(1.5,scene.duration_sec),settings.request_timeout_sec)
            warning=f"cảnh {scene.id} không có giọng đọc: TTS lỗi; dùng im lặng và caption. Chạy lại riêng audio cảnh {scene.id} trong Assets."
            meta={"audio_silent":True,"audio_error":message,"voice_used":None,"warnings":[warning]}
            write_json_atomic(audio_metadata_path(path),meta)
            from utils.word_timing import save_words
            save_words(path.with_suffix(".words.json"),scene.narration,duration)
            return duration,meta
        except Exception as silence_error:
            diagnostics.record_exception(silence_error,f"Không tạo được im lặng dự phòng cảnh {scene.id}")
            raise TTSError(f"{message}. Không tạo được audio dự phòng; kiểm tra quyền ghi audio/ và FFmpeg đi kèm, rồi chạy lại riêng audio cảnh {scene.id}.") from silence_error


def asset_writer(function):
    """UI retry and pipeline threads must not publish competing manifests."""
    @wraps(function)
    def locked(plan_path,*args,**kwargs):
        with path_lock(Path(plan_path).parent/"assets.write.lock"):
            return function(Path(plan_path),*args,**kwargs)
    return locked


@asset_writer
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
        protected_names=protected_tts_names(project)
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
            duration, audio=scene_audio(scene,original.voice,audio_path,settings,diagnostics,tts,protected_names)
            warnings.extend(audio["warnings"])
            resolved_scene=retime_scene(scene,duration,original.style_profile.shot_seconds.mean if original.style_profile else 3.)
            if len(resolved_scene.shots)!=len(scene.shots):
                warnings.append(f"Cảnh {scene.id}: số shot đổi từ {len(scene.shots)} thành {len(resolved_scene.shots)} theo audio thật.")
            if scene.role=="hook" and duration>3:
                warnings.append(f"Hook có audio thật {duration:.2f}s, vượt 3s; cần rút lời đọc nếu muốn hook ngắn hơn.")
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
                audio_duration_sec=duration, audio_error=audio["audio_error"],audio_silent=audio["audio_silent"],
                audio_voice=audio["voice_used"],audio_warnings=audio["warnings"],shots=shot_assets))
            if progress:
                progress(index + 1, len(original.scenes), f"Cảnh {scene.id}: đã chuẩn bị xong" + (" (KHÔNG CÓ GIỌNG ĐỌC — dùng im lặng và caption)" if audio["audio_silent"] else ""))
        data = {**original.model_dump(mode="json"), "scenes": scene_plans,
                "source_plan_hash": fingerprint, "warnings": warnings, "timing_basis": "audio"}
        resolved = ResolvedEditPlan.model_validate(data)
        if original.target_duration_sec and abs(resolved.duration_sec-original.target_duration_sec)>original.target_duration_sec*.1:
            # Director's validator REPAIRS duration/shot counts. Never run it on
            # audio-resolved plans: it invalidates the already-built manifest.
            warnings.append(f"Tổng thời lượng theo audio {resolved.duration_sec:.2f}s khác yêu cầu {original.target_duration_sec:.2f}s quá 10%; giữ nguyên timing audio, chưa tự đổi tốc độ giọng.")
        resolved.warnings = list(dict.fromkeys(warnings))
        manifest = AssetsManifest(source_plan_hash=fingerprint, resolved_plan_hash=cache_key(resolved.model_dump(mode="json")),
            status="complete",
            scenes=scene_assets, warnings=resolved.warnings)
        return persist(project, resolved, manifest, diagnostics,motion_enabled=settings.motion_enabled)
    except Exception as error:
        diagnostics.record_exception(error, "Assets pipeline failed")
        raise


def _remap_audio_shots(scene,record,duration,target=3.):
    """Reuse existing stock files; only timing and shot references are changed."""
    if not record.shots:
        raise ValueError(f"Cảnh {scene.id} không có stock để căn lại; chạy Tạo Assets cho project.")
    seed=scene.model_copy(deep=True)
    pool=[]
    for index,asset in enumerate(record.shots):
        shot=scene.shots[min(index,len(scene.shots)-1)].model_copy(deep=True)
        shot.query=asset.query
        shot.type={"video":"stock_video","image":"stock_image","color":"text_card"}[asset.media_type]
        pool.append(shot)
    seed.shots=pool
    updated=retime_scene(seed,duration,target)
    stock=[]
    for index,shot in enumerate(updated.shots):
        asset=record.shots[index%len(record.shots)].model_copy(deep=True)
        asset.shot_id=index+1
        if asset.media_type=="video":
            asset.requires_loop=bool(asset.media_duration_sec and asset.media_duration_sec<shot.duration_sec)
        stock.append(asset)
    record.shots=stock
    record.audio_duration_sec=duration
    return updated


def repair_asset_timings(resolved,manifest,project,diagnostics=None):
    """Repair old duration-validator damage without TTS or stock requests."""
    for index,scene in enumerate(resolved.scenes):
        record=next((r for r in manifest.scenes if r.scene_id==scene.id),None)
        if record is None or not record.audio_path: continue
        try:
            duration=audio_duration(safe_asset_path(project,record.audio_path))
        except Exception as error:
            if diagnostics: diagnostics.record_exception(error,f"TTS lỗi ở cảnh {scene.id}: audio cũ không đọc được")
            warning=f"TTS lỗi ở cảnh {scene.id}: audio cũ không đọc được ({type(error).__name__}); chạy lại riêng audio cảnh {scene.id}."
            record.audio_error=warning;record.audio_silent=False
            record.audio_warnings=list(dict.fromkeys(record.audio_warnings+[warning]))
            resolved.warnings.append(warning)
            continue
        if len(scene.shots)!=len(record.shots) or abs(scene.duration_sec-duration)>.02:
            resolved.scenes[index]=_remap_audio_shots(scene,record,duration)
            warning=f"Cảnh {scene.id}: sửa timing/shot từ manifest cũ theo audio thật {duration:.3f}s; tái sử dụng stock, không gọi TTS."
            resolved.warnings.append(warning)
    manifest.warnings=list(dict.fromkeys(resolved.warnings))
    resolved.warnings=list(manifest.warnings)


@asset_writer
def refresh_audio(plan_path:Path,settings:Settings,scene_id:int,*,tts=None)->Path:
    """Synthesize only the selected scene; never look up or download stock again."""
    diagnostics=assets_diagnostics(settings)
    try:
        original,resolved,manifest=load_assets(plan_path)
        source=next((s for s in original.scenes if s.id==scene_id),None)
        row=next((s for s in manifest.scenes if s.scene_id==scene_id),None)
        if source is None or row is None:
            raise ValueError(f"Không tìm thấy cảnh {scene_id}; tạo Assets trước khi thử lại audio riêng.")
        old_warnings=set(row.audio_warnings)
        duration,meta=scene_audio(source,original.voice,plan_path.parent/"audio"/f"scene_{scene_id}.mp3",
            settings,diagnostics,tts or EdgeTTSProvider(settings,diagnostics),protected_tts_names(plan_path.parent))
        scene=next(s for s in resolved.scenes if s.id==scene_id)
        updated=_remap_audio_shots(scene,row,duration,original.style_profile.shot_seconds.mean if original.style_profile else 3.)
        resolved.scenes=[updated if s.id==scene_id else s for s in resolved.scenes]
        row.audio_path=f"audio/scene_{scene_id}.mp3"
        row.audio_error=meta["audio_error"];row.audio_silent=meta["audio_silent"]
        row.audio_voice=meta["voice_used"];row.audio_warnings=meta["warnings"]
        resolved.warnings=[w for w in resolved.warnings if w not in old_warnings]
        resolved.warnings.extend(meta["warnings"])
        resolved.warnings=[w for w in resolved.warnings if not w.startswith("Tổng thời lượng theo audio ")]
        repair_asset_timings(resolved,manifest,plan_path.parent,diagnostics)
        if original.target_duration_sec and abs(resolved.duration_sec-original.target_duration_sec)>original.target_duration_sec*.1:
            resolved.warnings.append(f"Tổng thời lượng theo audio {resolved.duration_sec:.2f}s khác yêu cầu {original.target_duration_sec:.2f}s quá 10%; giữ nguyên timing audio.")
        manifest.warnings=list(dict.fromkeys(resolved.warnings))
        manifest.status="partial" if any(not s.audio_path or s.audio_error and not s.audio_silent for s in manifest.scenes) else "complete"
        return persist(plan_path.parent,resolved,manifest,diagnostics,motion_enabled=settings.motion_enabled)
    except Exception as error:
        diagnostics.record_exception(error,f"TTS lỗi ở cảnh {scene_id}: chạy lại riêng audio")
        raise


@asset_writer
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
        return persist(plan_path.parent, resolved, manifest, diagnostics,motion_enabled=settings.motion_enabled)
    except Exception as error:
        diagnostics.record_exception(error, f"Assets tìm lại cảnh {scene_id} shot {shot_id}")
        raise


def main() -> int:
    configure_console()
    logging.getLogger().setLevel(logging.CRITICAL)
    parser = argparse.ArgumentParser(description="Tạo Assets từ Edit Plan (chưa render)")
    parser.add_argument("edit_plan", type=Path)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--scene",type=int,help="Chỉ chạy lại audio cảnh có ID này, giữ stock/các cảnh khác")
    args = parser.parse_args()
    diagnostics = Diagnostics(Path(__file__).resolve().parents[1] / "logs", debug=args.debug, filename="assets_errors.log")
    try:
        if args.scene is not None:
            path=refresh_audio(args.edit_plan,get_settings(),args.scene)
        else:
            path = run_assets(args.edit_plan, get_settings(), debug=args.debug,
                progress=lambda done, total, text: print(f"[{done}/{total}] {text}"))
        manifest = AssetsManifest.model_validate(read_json(path))
    except Exception as error:
        diagnostics.record_exception(error, "Assets CLI failed")
        print("Không tạo được Assets: " + diagnostics.redact(str(error))[:1500])
        return 1
    fallbacks = sum(a.fallback for s in manifest.scenes for a in s.shots)
    print(f"Đã lưu: {path}; trạng thái={manifest.status}; shot fallback={fallbacks}.")
    for warning in manifest.warnings: print("Cảnh báo: "+diagnostics.redact(warning))
    print("Kế hoạch thời gian: edit_plan.resolved.json; nguồn: credits.txt. Chưa render video.")
    return 0 if manifest.status == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
