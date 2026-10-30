with open('app/views/ai_video.py', 'r', encoding='utf-8') as f:
    text = f.read()

approval_func = '''
def render_scene_director_approval(project: Path, settings, diagnostics):
    """Giai đoạn 8: Xem và duyệt prompt clip AI từ Scene Director."""
    sp_path = project / "scene_plan.json"
    if not sp_path.is_file():
        return

    try:
        from schemas.scene_director import ScenePlanResponse
        from pipeline.ai_clip_manager import estimate_ai_clips_cost, save_prompt_approvals, load_prompt_approvals
        from utils.atomic_io import write_json_atomic

        sp_data = json.loads(sp_path.read_text(encoding="utf-8"))
        scene_plan = ScenePlanResponse.model_validate(sp_data)
        approvals = load_prompt_approvals(project)

        ai_scenes = [sc for sc in scene_plan.scenes if sc.mode in ("ai_clip", "hybrid")]
        if not ai_scenes:
            st.info("Kế hoạch cảnh hiện tại (scene_plan.json) sử dụng 100% hoạt họa motion; không có clip AI nào cần tạo.")
            return

        st.subheader("🎬 Xem và duyệt prompt clip AI (Scene Director)")
        est = estimate_ai_clips_cost(scene_plan, settings)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Số clip AI", f"{len(ai_scenes)} / {len(scene_plan.scenes)} cảnh")
        c2.metric("Chế độ AI Clip", settings.ai_clip_mode.upper())
        c3.metric("Chi phí ước tính", f"{est['total_cost_vnd']:,} đ")
        c4.metric("Thời gian chờ", f"~{est['estimated_wait_sec']}s")

        # Load narration lookup from edit_plan if available
        narration_map = {}
        ep_path = project / "edit_plan.json"
        if ep_path.is_file():
            try:
                ep_data = json.loads(ep_path.read_text(encoding="utf-8"))
                for s in ep_data.get("scenes", []):
                    narration_map[s["id"]] = s.get("narration", "")
            except Exception:
                pass

        manual_dir = project / "ai_clips_manual"
        manual_dir.mkdir(parents=True, exist_ok=True)

        for sc in ai_scenes:
            with st.expander(f"Cảnh {sc.scene_id}: Chế độ {sc.mode.upper()} · Fallback: {sc.ai_clip.fallback_recipe}", expanded=True):
                if sc.scene_id in narration_map:
                    st.caption(f"Lời đọc: \\"{narration_map[sc.scene_id]}\\"")
                
                # Check manual clip presence
                from pipeline.ai_clip_manager import get_manual_clip_path
                existing_manual = get_manual_clip_path(project, sc.scene_id)
                if existing_manual:
                    st.success(f"Đã có clip nhập tay: {existing_manual.name} ({existing_manual.stat().st_size / 1024**2:.2f} MB)")

                current_p = sc.ai_clip.prompt_en if sc.ai_clip else ""
                new_p = st.text_area(f"Prompt tiếng Anh (Cảnh {sc.scene_id})", value=current_p, height=80, key=f"sp_p_{project.name}_{sc.scene_id}")
                
                col_a, col_b = st.columns([1, 1])
                approved_now = approvals.get(sc.scene_id, {}).get("approved", False)
                
                with col_a:
                    if st.checkbox("Đã duyệt prompt này", value=approved_now, key=f"chk_app_{project.name}_{sc.scene_id}"):
                        approvals[sc.scene_id] = {"approved": True, "prompt_en": new_p}
                    else:
                        approvals[sc.scene_id] = {"approved": False, "prompt_en": new_p}
                    save_prompt_approvals(project, approvals)

                with col_b:
                    if st.button(f"Bỏ qua clip, dùng motion (Cảnh {sc.scene_id})", key=f"skip_ai_{project.name}_{sc.scene_id}"):
                        sc.mode = "motion"
                        write_json_atomic(sp_path, scene_plan.model_dump(mode="json"))
                        st.success(f"Đã chuyển Cảnh {sc.scene_id} sang hoạt họa motion ({sc.ai_clip.fallback_recipe}).")
                        st.rerun()

                # Upload manual clip directly
                uploaded_f = st.file_uploader(f"Tải lên file video nhập tay (ai_clips_manual/scene_{sc.scene_id}.mp4)", type=["mp4", "mov"], key=f"up_man_{project.name}_{sc.scene_id}")
                if uploaded_f is not None:
                    dest = manual_dir / f"scene_{sc.scene_id}.mp4"
                    dest.write_bytes(uploaded_f.read())
                    st.success(f"Đã lưu clip nhập tay vào {dest.name}!")
                    st.rerun()

        st.divider()
    except Exception as exc:
        diagnostics.record_exception(exc, "UI Scene Director Approval")
        st.warning(f"Lỗi hiển thị duyệt prompt: {exc}")
'''

# Chèn hàm này trước hàm render
target_render = 'def render(settings,project,topic,debug,diagnostics):'
assert target_render in text, 'target_render not found'
text = text.replace(target_render, f'{approval_func}\n\n{target_render}', 1)

# Gọi hàm này ngay sau st.caption
target_call = 'st.caption("Tạo clip từ mô tả qua api.buihuuthang.com. Clip được lưu trong clips/, thông tin job trong ai_video/.")'
call_code = '''st.caption("Tạo clip từ mô tả qua api.buihuuthang.com. Clip được lưu trong clips/, thông tin job trong ai_video/.")
    if project:
        render_scene_director_approval(project, settings, local_diagnostics)'''

assert target_call in text, 'target_call not found'
text = text.replace(target_call, call_code, 1)

with open('app/views/ai_video.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Successfully integrated Scene Director Approval into app/views/ai_video.py')
