import json
import sys
from pathlib import Path

# Ensure video_ai_tool is on path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from PIL import Image, ImageDraw
from config.settings import get_settings
from schemas.edit_plan import EditPlan
from schemas.motion_scene import MotionScenePlan, VisualBeat
from utils.atomic_io import read_json_atomic, write_json_atomic
from editor.render import run_render
from tools.audit_video import audit_project
from agents.visual_diversity import repair_numeric_cards
from schemas.research_brief import ResearchBrief

def build_and_render_macbook():
    project_dir = ROOT_DIR / "output" / "auto-cong-nghe-d56d3ebe"
    assert project_dir.is_dir(), f"Project not found at {project_dir}"

    settings = get_settings().model_copy(
        update={
            "motion_recipes_enabled": True,
            "motion_enabled": True,
            "motion_scenes_enabled": True,
            "motion_scale": 0.5,
            "motion_fps": 30,
        }
    )

    plan_data = read_json_atomic(project_dir / "edit_plan.json")
    brief_data = read_json_atomic(project_dir / "brief.json") if (project_dir / "brief.json").is_file() else None
    plan = EditPlan.model_validate(plan_data)
    brief = ResearchBrief.model_validate(brief_data) if brief_data else None

    # Define verified data grounded in facts (6 distinct recipes, grounded numbers only)
    scenes_meta = [
        {
            "id": 1,
            "recipe": "before_after_wipe",
            "evidence": "Apple đã công bố dòng MacBook Pro trang bị màn hình OLED cảm ứng đầu tiên trong lịch sử của hãng.",
            "no_numbers": True,
            "data": {
                "label": "MacBook Pro OLED",
                "before_val": "Truyền thống",
                "after_val": "OLED cảm ứng",
                "source": "PetaPixel · VnExpress",
                "items": ["Laptop thường", "OLED cảm ứng", "Đột phá mới"]
            }
        },
        {
            "id": 2,
            "recipe": "gauge_needle",
            "evidence": "Màn hình PROLED XDR đạt độ sáng đỉnh hai nghìn nit cùng tần số quét 120Hz.",
            "no_numbers": False,
            "data": {
                "label": "Tần số quét màn hình",
                "value": 120,
                "unit": "Hz",
                "source": "PetaPixel · VnExpress",
                "items": ["Màn hình OLED", "Tần số 120Hz", "Độ sáng 2.000 nit"]
            }
        },
        {
            "id": 3,
            "recipe": "slot_counter",
            "evidence": "phiên bản MacBook Pro 14 inch trang bị chip M6 sản xuất trên tiến trình 2nm với giá khởi điểm tại Việt Nam là 54.999.000 VND",
            "no_numbers": False,
            "data": {
                "label": "Tiến trình Chip M6",
                "value": 2,
                "unit": "nm",
                "digits": 1,
                "source": "Minh Tuấn Mobile",
                "items": ["Chip M6", "Tiến trình 2nm", "Giá 54,99 triệu"]
            }
        },
        {
            "id": 4,
            "recipe": "puzzle_snap",
            "evidence": "MacBook Pro mới chuyển từ thiết kế tai thỏ sang hệ thống camera dạng Dynamic Island.",
            "no_numbers": True,
            "data": {
                "label": "Nâng cấp Dynamic Island",
                "piece_left": "Tai thỏ cũ",
                "piece_right": "Dynamic Island",
                "source": "PetaPixel · VnExpress",
                "items": ["Tai thỏ cũ", "Dynamic Island", "Gọn gàng hiện đại"]
            }
        },
        {
            "id": 5,
            "recipe": "balance_scale",
            "evidence": "MacBook Pro OLED cảm ứng có giá khởi điểm 80 triệu đồng cho bản 14 inch... tại thị trường Mỹ.",
            "no_numbers": False,
            "data": {
                "label": "Cân nhắc nâng cấp",
                "value": 80,
                "unit": "triệu VND",
                "left_label": "Khởi điểm",
                "left_val": "80 triệu",
                "right_label": "Trải nghiệm",
                "right_val": "OLED cảm ứng",
                "winner": "right",
                "source": "VnExpress",
                "items": ["Giá 80 triệu", "Trải nghiệm OLED", "Đáng nâng cấp?"]
            }
        },
        {
            "id": 6,
            "recipe": "shield_hit",
            "evidence": "lớp kính bảo vệ cực bền nhưng vẫn phải giữ độ mỏng nhẹ",
            "no_numbers": True,
            "data": {
                "label": "Độ bền kính bảo vệ",
                "hits": 3,
                "source": "PetaPixel · VnExpress",
                "items": ["Kính siêu bền", "Mỏng nhẹ", "Cảm ứng nhạy"]
            }
        }
    ]

    for sc, meta in zip(plan.scenes, scenes_meta):
        vp = MotionScenePlan(
            scene_type=meta["recipe"],
            motion_recipe=meta["recipe"],
            layout="center_hero",
            zone="middle",
            evidence=meta["evidence"],
            no_numbers=meta["no_numbers"],
            theme="neon_dark",
            data=meta["data"],
            beats=[
                VisualBeat(action="reveal", at_sec=0.2),
                VisualBeat(action="action", at_sec=1.0),
                VisualBeat(action="impact", at_sec=2.5),
            ],
            annotations=[]
        )
        sc.visual_plan = vp

    # Run repair_numeric_cards to ensure absolute grounding compliance
    repair_numeric_cards(plan, brief)

    # Save plan and resolved
    write_json_atomic(project_dir / "edit_plan.json", plan.model_dump(mode="json"))

    resolved_path = project_dir / "edit_plan.resolved.json"
    if resolved_path.is_file():
        resolved_data = read_json_atomic(resolved_path)
        for r_sc, p_sc in zip(resolved_data.get("scenes", []), plan.scenes):
            if p_sc.visual_plan:
                r_sc["visual_plan"] = p_sc.visual_plan.model_dump(mode="json")
                for sh in r_sc.get("shots", []):
                    if "visual" in sh and sh["visual"]:
                        sh["visual"]["template"] = "text_focus"
                        if "data" in sh["visual"]:
                            sh["visual"]["data"]["bars"] = []
                            sh["visual"]["data"]["value"] = None
        write_json_atomic(resolved_path, resolved_data)

        assets_path = project_dir / "assets.json"
        if assets_path.is_file():
            from utils.cache import cache_key
            assets_data = read_json_atomic(assets_path)
            assets_data["resolved_plan_hash"] = cache_key(resolved_data)
            write_json_atomic(assets_path, assets_data)

    print("=== Running run_render at scale 0.5 ===")
    video_res = run_render(
        resolved_path if resolved_path.is_file() else project_dir / "edit_plan.json",
        mode="preview",
        settings=settings,
    )
    print(f"Render completed: {video_res}")

    print("=== Running Video Audit ===")
    audit_res = audit_project(project_dir, force=True)
    print(f"Audit overall passed: {audit_res.get('overall_all_passed')}")

    # Build Contact Sheet (6 scenes)
    print("=== Generating Contact Sheet ===")
    review_dir = project_dir / "review_frames"
    review_dir.mkdir(parents=True, exist_ok=True)

    motion_cache = project_dir / "render" / "motion_cache"
    scene_frames = {}
    if motion_cache.is_dir():
        for f in motion_cache.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                sid = data.get("scene_id")
                png_path = f.with_suffix(".png")
                if sid and png_path.is_file() and sid not in scene_frames:
                    scene_frames[sid] = png_path
            except Exception:
                pass

    if len(scene_frames) >= 6:
        thumbs = [Image.open(scene_frames[i]).resize((360, 640)) for i in range(1, 7)]
        sheet = Image.new("RGB", (360 * 3, 640 * 2), (15, 23, 42))
        for idx, thumb in enumerate(thumbs):
            r = idx // 3
            c = idx % 3
            sheet.paste(thumb, (c * 360, r * 640))
        out_sheet = review_dir / "contact_sheet.png"
        sheet.save(out_sheet)
        print(f"Contact sheet saved to {out_sheet}")

        # Also save to artifact directory
        artifact_path = Path(r"C:\Users\admin\.gemini\antigravity\brain\9c8d69ff-e905-4ac2-97dc-25baf1a541df\contact_sheet_macbook_oled_clean.png")
        sheet.save(artifact_path)
        print(f"Artifact contact sheet updated at {artifact_path}")

    return audit_res

if __name__ == "__main__":
    build_and_render_macbook()
