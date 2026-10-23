"""Adapt existing AI job outputs to a separate render bundle; originals stay intact."""
from pathlib import Path
from pipeline.ai_video import create_job,resume_job
from pipeline.assets import load_assets,safe_asset_path
from editor.timeline import confined
from providers.video_gateway import VideoRequest
from utils.cache import cache_key,write_json
from utils.atomic_io import copy_file_atomic, write_text_atomic
from utils.source_credits import source_credit_lines
from agents.video_prompt_writer import validate_ai_prompt,fallback_prompt
from providers.video_gateway import GatewayVideoError
from pipeline.projects import read_json
from utils.plan_lookup import shot_lookup


def copy_artifact(source,destination):
    return copy_file_atomic(source, destination)


def prepare_ai_bundle(project,config,settings,progress,check_cancel,diagnostics):
    original,resolved,manifest = load_assets(project/"edit_plan.json")
    originals = shot_lookup(original)
    resolved_shots = shot_lookup(resolved)
    slots = []
    for scene in manifest.scenes:
        for shot in scene.shots:
            key = (scene.scene_id, shot.shot_id)
            warning = None
            if key not in resolved_shots:
                warning = f"Không tìm thấy shot resolved: cảnh {key[0]} / shot {key[1]}; bỏ qua slot AI."
            elif key not in originals:
                warning = f"Không tìm thấy shot gốc: cảnh {key[0]} / shot {key[1]}; coi là shot không phải ai_video."
            if warning:
                diagnostics.record(warning)
                manifest.warnings.append(warning)
                progress(0., warning)
            if key in resolved_shots:
                slots.append((scene, shot))
    slots.sort(key=lambda pair:(
        getattr(originals.get((pair[0].scene_id, pair[1].shot_id)), "type", None) != "ai_video",
        not pair[1].fallback, pair[0].scene_id, pair[1].shot_id))
    if len(slots) < config.ai_clips:
        raise ValueError(f"Kế hoạch chỉ có {len(slots)} shot, không đủ để dùng {config.ai_clips} clip AI đã chọn; chưa gửi yêu cầu trả phí.")
    used = []
    for index,(scene_asset,shot_asset) in enumerate(slots[:config.ai_clips],1):
        check_cancel()
        scene = next(scene for scene in resolved.scenes if scene.id == scene_asset.scene_id)
        shot = resolved_shots[(scene.id, shot_asset.shot_id)]
        original_shot = originals.get((scene.id, shot_asset.shot_id))
        prompt = getattr(original_shot, "ai_prompt", None)
        ai_prompt = validate_ai_prompt(prompt) if prompt is not None else fallback_prompt(original.title)
        request = VideoRequest(model=config.ai_model,seconds=config.ai_seconds,format=config.video_format,
            prompt=ai_prompt)
        # A changed prompt is a NEW paid request. An old failed/ambiguous slot
        # must be reconciled, or explicitly created through the paid UI first.
        key = cache_key(request.model_dump(mode="json"))
        receipt = confined(project,f"ai_video/slot_{scene.id}_{shot_asset.shot_id}.receipt")
        expected_job = confined(project,f"ai_video/{key}.json")
        if receipt.exists() and read_json(receipt)["request_hash"] != key and not expected_job.exists():
            raise GatewayVideoError("Prompt đã đổi sau lần gửi trước. Job cũ có thể vẫn tính phí; xác nhận tạo job mới trên trang AI Video rồi tiếp tục pipeline.")
        write_json(receipt,{"request_hash":key,"scene_id":scene.id,"shot_id":shot_asset.shot_id})
        # Existing job helper durably deduplicates POST, including after a lost
        # response. Resume never silently creates an extra paid job.
        job_path = create_job(project,request,settings)
        check_cancel()
        result = resume_job(job_path,settings,progress=lambda fraction,message:progress(((index-1)+fraction)/config.ai_clips,message))
        job_path = Path(result.get("effective_job_path",job_path))
        used.append({"scene_id":scene.id,"shot_id":shot_asset.shot_id,"model":config.ai_model,"seconds":config.ai_seconds,
                     "job_path":job_path.relative_to(project).as_posix(),"remote_id":result["remote_id"],"clip_path":result["clip_path"],
                     "actual_cost_vnd":result.get("actual_cost_vnd"),"duration_sec":result["duration_sec"]})
        shot.type = "ai_video"
        shot.ai_prompt = ai_prompt
        shot_asset.path = result["clip_path"]
        shot_asset.media_type = "video"
        shot_asset.provider = "generated"
        shot_asset.asset_id = result["remote_id"]
        shot_asset.author = "AI-generated / "+config.ai_model
        shot_asset.source_url = "https://api.buihuuthang.com/docs/video"
        shot_asset.media_duration_sec = result["duration_sec"]
        shot_asset.requires_loop = result["duration_sec"] < shot.duration_sec
        shot_asset.fallback,shot_asset.fallback_reason = False,None
    check_cancel()
    bundle = confined(project,"ai_render")
    bundle.mkdir(exist_ok=True)
    copy_artifact(project/"edit_plan.json",confined(bundle,"edit_plan.json"))
    for scene in manifest.scenes:
        if not scene.audio_path:
            raise ValueError(f"Thiếu audio cảnh {scene.scene_id}; chạy lại Assets.")
        copy_artifact(safe_asset_path(project,scene.audio_path),confined(bundle,scene.audio_path))
        for shot in scene.shots:
            copy_artifact(safe_asset_path(project,shot.path),confined(bundle,shot.path))
    manifest.resolved_plan_hash = cache_key(resolved.model_dump(mode="json"))
    write_json(confined(bundle,"edit_plan.resolved.json"),resolved.model_dump(mode="json"))
    write_json(confined(bundle,"assets.json"),manifest.model_dump(mode="json"))
    ai_slots = {(item["scene_id"],item["shot_id"]):item for item in used}
    lines = ["CREDITS — tài nguyên trong bản dựng có clip AI",""]
    for scene in manifest.scenes:
        lines.append(f"Cảnh {scene.scene_id}: audio có đoạn im lặng do TTS lỗi; dùng caption." if scene.audio_silent else
            f"Cảnh {scene.scene_id}: giọng đọc Microsoft Edge TTS ({scene.audio_voice or original.voice}).")
        for shot in scene.shots:
            label = f"Cảnh {scene.scene_id} / shot {shot.shot_id}"
            ai = ai_slots.get((scene.scene_id,shot.shot_id))
            if ai:
                lines.extend([f"{label}: AI-generated, gateway api.buihuuthang.com, model {ai['model']}, job {ai['remote_id']}.",f"File: {shot.path}"])
            elif shot.provider == "generated":
                lines.append(f"{label}: nền màu/chữ tạo bằng code. File: {shot.path}")
            else:
                lines.extend([f"{label}: {shot.provider} — tác giả {shot.author}",f"Nguồn: {shot.source_url}",f"File: {shot.path}"])
    lines.extend(["","Pixabay: https://pixabay.com/service/license-summary/","Pexels: https://www.pexels.com/license/"])
    lines.extend(source_credit_lines(project))
    write_text_atomic(confined(bundle,"credits.txt"), diagnostics.redact("\n".join(lines)+"\n"))
    return bundle/"edit_plan.resolved.json",used
