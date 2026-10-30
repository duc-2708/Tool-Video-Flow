import sys
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from config.settings import get_settings
from schemas.scene_director import ScenePlanResponse
from pipeline.ai_clip_manager import resolve_scene_ai_clip, get_manual_clip_path, estimate_ai_clips_cost

def main():
    project_dir = ROOT / "output" / "auto-cong-nghe-d56d3ebe"
    sp_file = project_dir / "scene_plan.json"
    assert sp_file.is_file(), "scene_plan.json not found"

    scene_plan = ScenePlanResponse.model_validate(json.loads(sp_file.read_text(encoding="utf-8")))
    ai_scene = next(s for s in scene_plan.scenes if s.scene_id == 1)

    print("=== 1. Ước tính chi phí AI Clip ===")
    settings = get_settings().model_copy(update={"ai_clips_max_per_video": 2, "ai_clip_model": "veo-3.1"})
    est = estimate_ai_clips_cost(scene_plan, settings)
    print(f"Số clip AI đủ điều kiện: {est['count']}")
    print(f"Chi phí ước tính: {est['total_cost_vnd']:,} VNĐ ({est['unit_cost_vnd']:,} VNĐ/clip)")
    print(f"Thời gian chờ dự kiến: ~{est['estimated_wait_sec']}s")

    print("\n=== 2. Kiểm tra chế độ AI_CLIP_MODE='off' ===")
    settings_off = settings.model_copy(update={"ai_clip_mode": "off"})
    res_off = resolve_scene_ai_clip(project_dir, ai_scene, settings=settings_off)
    print(f"Resolved: {res_off['resolved']}")
    print(f"Fallback to motion: {res_off['fallback_to_motion']}")
    print(f"Recipe fallback: {res_off['recipe']}")
    print(f"Lý do: {res_off['reason']}")

    print("\n=== 3. Kiểm tra chế độ AI_CLIP_MODE='manual' với clip nhập tay ===")
    manual_dir = project_dir / "ai_clips_manual"
    manual_dir.mkdir(parents=True, exist_ok=True)

    # Tìm một file mp4 có sẵn làm clip mẫu nhập tay (không tốn phí)
    sample_mp4 = None
    gallery_dir = ROOT / "output" / "recipe_gallery"
    if gallery_dir.is_dir():
        for f in gallery_dir.glob("*.mp4"):
            if f.stat().st_size > 5000:
                sample_mp4 = f
                break
    if not sample_mp4:
        for f in (ROOT / "output").glob("**/*.mp4"):
            if f.stat().st_size > 5000:
                sample_mp4 = f
                break

    target_manual_file = manual_dir / "scene_1.mp4"
    if sample_mp4:
        shutil.copy2(sample_mp4, target_manual_file)
        print(f"Đã sao chép clip mẫu ({sample_mp4.name}) vào {target_manual_file.relative_to(ROOT)}")
    else:
        target_manual_file.write_bytes(b"\x00" * 2048)
        print("Đã tạo clip giả lập trong ai_clips_manual")

    settings_manual = settings.model_copy(update={"ai_clip_mode": "manual"})
    res_manual = resolve_scene_ai_clip(project_dir, ai_scene, settings=settings_manual)
    print(f"Resolved: {res_manual['resolved']}")
    print(f"Source: {res_manual['source']}")
    print(f"AI generated: {res_manual['ai_generated']}")
    print(f"Label: {res_manual['label']}")
    print(f"Clip path: {res_manual['clip_path']}")
    print(f"Fallback to motion: {res_manual['fallback_to_motion']}")

if __name__ == "__main__":
    main()
