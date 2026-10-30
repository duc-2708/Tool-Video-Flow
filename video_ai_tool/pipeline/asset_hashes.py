"""
Asset dependency-separated hashing and change detection.
Ensures audio, AI clips, and visual plans have independent hashes so visual edits
do not invalidate voice synthesis or expensive AI clips.
"""
from pathlib import Path
from typing import Any
from utils.cache import cache_key
from schemas.edit_plan import EditPlan, Scene, Shot
from schemas.assets import AssetsManifest


def compute_scene_audio_hash(scene: Scene, voice: str, tts_speed: str | None = None) -> str:
    """Compute hash exclusively for voice narration of a specific scene."""
    data = {
        "id": scene.id,
        "narration": " ".join(scene.narration.strip().split()),
        "voice": voice,
        "pronunciation_hint": getattr(scene, "pronunciation_hint", None) or "",
        "tts_speed": tts_speed or ""
    }
    return cache_key(data)


def compute_audio_hash(plan: EditPlan) -> str:
    """Compute aggregate audio hash for the entire edit plan."""
    voice = getattr(plan, "voice", "vi-VN-HoaiMyNeural")
    scene_hashes = [compute_scene_audio_hash(s, voice) for s in plan.scenes]
    return cache_key({"voice": voice, "scenes": scene_hashes})


def compute_scene_clip_hash(scene: Scene) -> str:
    """Compute hash for AI video clips or b-roll prompts in a scene."""
    clip_data = []
    for idx, shot in enumerate(scene.shots):
        clip_data.append({
            "shot_idx": idx + 1,
            "ai_prompt": getattr(shot, "ai_prompt", None) or "",
            "query": getattr(shot, "query", "") or "",
            "type": getattr(shot, "type", "") or ""
        })
    return cache_key(clip_data)


def compute_clip_hash(plan: EditPlan) -> str:
    """Compute aggregate AI clip hash for the entire edit plan."""
    return cache_key([compute_scene_clip_hash(s) for s in plan.scenes])


def compute_visual_hash(plan: Any) -> str:
    """
    Compute hash for motion graphics and visual layout.
    Changes here do NOT invalidate audio synthesis or AI b-roll clips.
    """
    vis_data = []
    scenes = getattr(plan, "scenes", [])
    for s in scenes:
        vp = getattr(s, "visual_plan", None)
        vp_dump = vp.model_dump(mode="json") if hasattr(vp, "model_dump") else (dict(vp) if isinstance(vp, dict) else None)
        shot_vis = []
        for sh in getattr(s, "shots", []):
            sh_vp = getattr(sh, "visual_plan", None)
            sh_vp_dump = sh_vp.model_dump(mode="json") if hasattr(sh_vp, "model_dump") else (dict(sh_vp) if isinstance(sh_vp, dict) else None)
            shot_vis.append({
                "template": getattr(getattr(sh, "visual", None), "template", None),
                "visual_plan": sh_vp_dump,
                "card_text": getattr(sh, "card_text", None) or ""
            })
        vis_data.append({
            "scene_id": getattr(s, "id", None),
            "visual_plan": vp_dump,
            "shots": shot_vis
        })
    return cache_key(vis_data)


def source_script_hash(plan: EditPlan) -> str:
    """
    Hash of the structural script content (title, format, voice, scene roles, narration).
    Excludes all visual_plan, recipe, beats, emphasis, repair_notes and extra metadata.
    """
    data = {
        "title": getattr(plan, "title", ""),
        "format": getattr(plan, "format", "tiktok"),
        "voice": getattr(plan, "voice", "vi-VN-HoaiMyNeural"),
        "scenes": [
            {
                "id": s.id,
                "role": s.role,
                "narration": " ".join(s.narration.strip().split()),
                "pronunciation_hint": getattr(s, "pronunciation_hint", None) or ""
            }
            for s in plan.scenes
        ]
    }
    return cache_key(data)


def detect_plan_changes(manifest: AssetsManifest | None, current_plan: EditPlan) -> dict:
    """
    Inspect what changed between manifest and current plan:
    - Audio changes: which scenes had their narration or voice changed.
    - Clip changes: which scenes had their ai_prompt changed.
    - Visual-only changes: recipe, beats, layout changed without voice/clip modifications.
    """
    res = {
        "audio_changed": False,
        "changed_audio_scenes": [],
        "voice_changed": None,
        "clips_changed": [],
        "visual_only_changed": False,
        "explanation": [],
        "cost_estimate": {"estimated_cost_usd": 0.0, "estimated_time_sec": 0}
    }
    if manifest is None:
        res["audio_changed"] = True
        res["explanation"].append("Chưa có Assets manifest")
        return res

    current_voice = getattr(current_plan, "voice", "vi-VN-HoaiMyNeural")
    current_audio_hash = compute_audio_hash(current_plan)

    # 1. Check voice change
    manifest_voice = None
    if manifest.scenes and manifest.scenes[0].audio_voice:
        manifest_voice = manifest.scenes[0].audio_voice
    if manifest_voice and manifest_voice != current_voice:
        res["audio_changed"] = True
        res["voice_changed"] = (manifest_voice, current_voice)
        res["explanation"].append(f"Giọng đọc đổi từ '{manifest_voice}' sang '{current_voice}'")

    # 2. Check scene-level narration changes
    old_scene_hashes = getattr(manifest, "scene_audio_hashes", {}) or {}
    if old_scene_hashes:
        for sc in current_plan.scenes:
            cur_sc_hash = compute_scene_audio_hash(sc, current_voice)
            if str(sc.id) in old_scene_hashes or sc.id in old_scene_hashes:
                if old_scene_hashes.get(str(sc.id), old_scene_hashes.get(sc.id)) != cur_sc_hash:
                    res["audio_changed"] = True
                    res["changed_audio_scenes"].append(sc.id)
                    res["explanation"].append(f"Cảnh {sc.id}: Lời đọc kịch bản đã thay đổi")
            else:
                res["audio_changed"] = True
                res["changed_audio_scenes"].append(sc.id)
                res["explanation"].append(f"Cảnh {sc.id}: Kịch bản mới chưa có audio")
    else:
        cur_source_hash = source_script_hash(current_plan)
        if manifest.source_plan_hash and manifest.source_plan_hash != cur_source_hash and manifest.source_plan_hash != "fixture":
            res["audio_changed"] = True
            res["explanation"].append("Kịch bản hoặc giọng đọc đã thay đổi")

    # If manifest had aggregate audio_hash
    if getattr(manifest, "audio_hash", None) and manifest.audio_hash != current_audio_hash:
        res["audio_changed"] = True

    # 3. Check AI Clip prompt changes
    old_clip_hashes = getattr(manifest, "scene_clip_hashes", {}) or {}
    for sc in current_plan.scenes:
        cur_c_hash = compute_scene_clip_hash(sc)
        if (str(sc.id) in old_clip_hashes or sc.id in old_clip_hashes) and old_clip_hashes.get(str(sc.id), old_clip_hashes.get(sc.id)) != cur_c_hash:
            res["clips_changed"].append(sc.id)
            res["explanation"].append(f"Cảnh {sc.id}: Prompt clip AI hoặc b-roll đã thay đổi")

    # Calculate cost estimate for changed AI clips
    if res["clips_changed"]:
        num_clips = len(res["clips_changed"])
        res["cost_estimate"]["estimated_cost_usd"] = round(num_clips * 0.05, 2)
        res["cost_estimate"]["estimated_time_sec"] = num_clips * 60

    # 4. Check if changes are purely visual
    if not res["audio_changed"] and not res["clips_changed"]:
        res["visual_only_changed"] = True
        res["explanation"].append("Kịch bản và clip không đổi; chỉ cập nhật công thức hoạt họa (recipe/visual)")

    return res
