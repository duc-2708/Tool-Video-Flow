"""Prompt-only edits with concurrency checks; never changes existing paid jobs."""
import hashlib
from pathlib import Path
from agents.video_prompt_writer import validate_ai_prompt
from pipeline.projects import read_json
from schemas.edit_plan import EditPlan
from utils.atomic_io import write_json_atomic
from utils.file_lock import file_lock
from utils.plan_lookup import shot_lookup


def save_shot_prompt(project,scene_id,shot_index,prompt):
    prompt = validate_ai_prompt(prompt)
    if shot_index < 1:
        raise ValueError("Shot được đánh số từ 1.")
    project = Path(project).resolve()
    path = project/"edit_plan.json"
    with file_lock(project/"run_all.lock",timeout=0):
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        plan = EditPlan.model_validate(read_json(path))
        shot = shot_lookup(plan).get((scene_id, shot_index))
        if shot is None:
            raise ValueError(f"Không tìm thấy cảnh {scene_id} / shot {shot_index} trong Edit Plan.")
        if shot.type != "ai_video":
            raise ValueError("Chỉ lưu ai_prompt cho shot ai_video; tạo lại Director nếu cần đổi loại shot.")
        state_path = project/"run_state.json"
        state = read_json(state_path) if state_path.exists() else None
        if state is not None:
            expected = state["steps"]["director"].get("artifacts",{}).get("edit_plan.json")
            if expected and expected != before:
                raise ValueError("Edit Plan đã thay đổi ngoài checkpoint; kiểm tra/lưu kịch bản trước khi sửa prompt.")
            if state["steps"]["ai_video"]["status"] == "done" or state["steps"]["render"]["status"] == "done":
                raise ValueError("Pipeline đã dùng clip/render; prompt mới cần một project mới để không thay metadata của bản dựng cũ.")
        shot.ai_prompt = prompt
        write_json_atomic(path,plan.model_dump(mode="json"))
        if state is not None and expected:
            state["steps"]["director"]["artifacts"]["edit_plan.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
            write_json_atomic(state_path,state)
    return path
