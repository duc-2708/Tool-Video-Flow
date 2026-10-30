"""Opt-in text-to-video UI for Veo and Seedance through Hinton gateway."""
import json
from pathlib import Path
import streamlit as st
from providers.video_gateway import MODELS,allowed_models,VideoRequest,VideoGateway
from pipeline.ai_video import load_job,diagnostics_for
from pipeline.ai_video_jobs import AIVideoJobs
from editor.timeline import confined
from pipeline.projects import read_json
from schemas.edit_plan import EditPlan
from app.ai_prompt_controls import prompt_editor
from agents.video_prompt_writer import fallback_prompt,validate_ai_prompt,write_video_prompt
from agents.director import director_provider
from pipeline.video_prompts import save_shot_prompt


@st.cache_resource
def ai_video_jobs():
    return AIVideoJobs()


def failed_job_details(data, diagnostics):
    if not (data.get("error") or data.get("gateway_failure") or data.get("generation_retry_count")):
        return
    request = data.get("sent_payload") or data.get("request",{})
    ratio = request.get("aspect_ratio") or ("9:16" if request.get("format") == "tiktok" else "16:9")
    st.caption(f"Đã gửi · model {request.get('model')} · {request.get('seconds')} giây · {ratio}")
    with st.expander("Prompt đã gửi và chi tiết lỗi gateway", expanded=True):
        st.code(diagnostics.redact(request.get("prompt", "")),language="text")
        if data.get("gateway_failure"):
            st.json(diagnostics.redact(json.dumps(data["gateway_failure"],ensure_ascii=False)))
        if data.get("generation_retry_path"):
            st.caption("Job thử lại: " + data["generation_retry_path"])
        st.info("Nguyên nhân thường gặp: bộ lọc nội dung/quyền hình ảnh, prompt quá phức tạp, tham số model không hỗ trợ hoặc lỗi nhà cung cấp. Đây là gợi ý; generation_failed chung chưa đủ xác định nguyên nhân.")


def recovery_controls(project, selected, data, settings, *, disabled=False, key_prefix="ai_recovery"):
    """Shared by AI Video and one-button pipeline; no requests on page load."""
    manager = ai_video_jobs()
    active = disabled or bool(manager.active(project))
    present = bool(settings.gateway_api_key.get_secret_value().strip())
    worker_key = f"ai_video_worker_{project.name}"
    if data.get("remote_id"):
        return
    nonce_key = f"{key_prefix}_{selected.stem}_confirmation_nonce"
    nonce = st.session_state.get(nonce_key,0)
    st.error("Job chưa có remote ID. Kiểm tra dashboard gateway trước khi chọn cách khôi phục.")
    remote_id = st.text_input("Remote ID từ dashboard",key=f"{key_prefix}_{selected.stem}_id").strip()
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    st.caption("Chạy tại thư mục video_ai_tool. Lệnh tiếp tục job đã có; riêng generation_failed có thể tạo tối đa 1 job thử lại có phí. Timeout/thiếu ID không tự tạo lại.")
    st.code(".\\.venv\\Scripts\\python.exe -m pipeline.ai_video resume " + quote(selected) +
            " --remote-id " + quote(remote_id or "DÁN_REMOTE_ID_VÀO_ĐÂY"),language="powershell")
    if st.button("Tiếp tục job có sẵn",disabled=active or not present or not remote_id,key=f"{key_prefix}_{selected.stem}_resume"):
        st.session_state[worker_key] = manager.submit(project,None,settings,job_path=selected,remote_id=remote_id)
        st.rerun()
    st.warning("Tạo lại có thể phát sinh thêm chi phí nếu job cũ thực tế đã được tạo. Bỏ qua clip AI không hủy hoặc hoàn tiền job cũ.")
    confirmed = st.checkbox("Tôi đã kiểm tra dashboard: không có job; chấp nhận chi phí có thể phát sinh khi tạo lại",
        key=f"{key_prefix}_{selected.stem}_confirm_{nonce}")
    if st.button("Đã kiểm tra dashboard: không có job, tạo lại",disabled=active or not present or not confirmed,
            key=f"{key_prefix}_{selected.stem}_recreate"):
        st.session_state[worker_key] = manager.submit(project,None,settings,job_path=selected,recreate_confirmed=True)
        # Prevent another paid submission without checking the box again.
        st.session_state[nonce_key] = nonce+1
        st.rerun()



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
                    st.caption(f"Lời đọc: \"{narration_map[sc.scene_id]}\"")
                
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


def render(settings,project,topic,debug,diagnostics):
    st.header("AI Video · Veo / Seedance")
    st.caption("generation_failed sẽ tự thử lại tối đa 1 job bằng prompt an toàn; có thể phát sinh thêm chi phí. Timeout/thiếu ID không tự tạo lại.")
    st.caption("Tạo clip từ mô tả qua api.buihuuthang.com. Clip được lưu trong clips/, thông tin job trong ai_video/.")
    if project:
        render_scene_director_approval(project, settings, diagnostics or diagnostics_for(settings))
    if project is None:
        st.info("Chọn project trong sidebar. Có thể tạo project ở trang Research trước.")
        return
    local_diagnostics = diagnostics or diagnostics_for(settings)
    present = bool(settings.gateway_api_key.get_secret_value().strip())
    if not present:
        st.warning("Chưa có GATEWAY_API_KEY trong cấu hình local.")
    if st.button("Kiểm tra kết nối và model",disabled=not present):
        client = None
        try:
            with st.spinner("Đang lấy danh sách model; không tạo video..."):
                client = VideoGateway(settings,local_diagnostics)
                names = [m["id"] for m in client.models()]
                st.success("Kết nối thành công. Model trong catalogue: "+", ".join(names))
        except Exception as error:
            local_diagnostics.record_exception(error,"UI kiểm tra gateway")
            st.error(local_diagnostics.redact(str(error)))
        finally:
            if client:
                client.close()
    names = allowed_models(settings)
    if not names:
        st.error("GATEWAY_ALLOWED_MODELS không có model được hỗ trợ: veo-3.1, seedance-2.5-30s.")
        return
    default = names.index(settings.gateway_video_model) if settings.gateway_video_model in names else 0
    model = st.selectbox("Model tạo video",names,index=default,key="ai_video_model")
    seconds = st.selectbox("Thời lượng clip (giây)",MODELS[model],index=MODELS[model].index(settings.ai_clip_seconds) if settings.ai_clip_seconds in MODELS[model] else 0,key=f"ai_video_seconds_{model}")
    format_name = st.selectbox("Khổ video",["tiktok","youtube"],format_func=lambda item:"Dọc 9:16" if item == "tiktok" else "Ngang 16:9",key="ai_video_format")
    resolution = st.selectbox("Độ phân giải",["720p","1080p"] if model == "veo-3.1" else ["720p"],key=f"ai_video_resolution_{model}")
    slots = []
    plan_path = project/"edit_plan.json"
    if plan_path.exists():
        try:
            plan = EditPlan.model_validate(read_json(plan_path))
            slots = [(scene,index,shot) for scene in plan.scenes for index,shot in enumerate(scene.shots,1) if shot.type == "ai_video"]
        except (OSError,ValueError) as error:
            st.warning(local_diagnostics.redact(str(error)))
    selection = st.selectbox("Shot clip AI",[None,*range(len(slots))],index=1 if slots else 0,
        format_func=lambda value:"Clip độc lập" if value is None else f"Cảnh {slots[value][0].id} / shot {slots[value][1]}",key=f"ai_prompt_shot_{project.name}")
    if selection is not None:
        scene,shot_index,shot = slots[selection]
        prompt,prompt_key = prompt_editor(settings,project,scene.id,shot_index,shot.ai_prompt,plan.title,local_diagnostics,prefix="ai_video")
    else:
        prompt_key = f"ai_video_prompt_{project.name}"
        pending = st.session_state.pop(prompt_key+"_pending",None)
        if pending is not None:
            st.session_state[prompt_key] = pending
        prompt = st.text_area("Mô tả clip",value=fallback_prompt(topic),height=120,key=prompt_key)
        simpler = st.checkbox("Đơn giản hơn",key=prompt_key+"_simpler")
        from providers.llm.router import route_ready
        if st.button("Viết lại prompt",key=prompt_key+"_rewrite",disabled=not route_ready(settings,"director")):
            client = None
            try:
                client = director_provider(settings,local_diagnostics)
                st.session_state[prompt_key+"_pending"] = write_video_prompt({"topic":topic[:120],"narration":prompt[:400]},client,local_diagnostics,simpler=simpler)
                st.rerun()
            except Exception as error:
                local_diagnostics.record_exception(error,"UI viết lại prompt clip độc lập")
                st.error(local_diagnostics.redact(str(error)))
            finally:
                if client:
                    client.close()
    manager = ai_video_jobs()
    active = manager.active(project)
    state_key = f"ai_video_worker_{project.name}"
    request = None
    try:
        if prompt.strip():
            request = VideoRequest(model=model,prompt=validate_ai_prompt(prompt),seconds=seconds,format=format_name,resolution=resolution)
    except Exception as error:
        st.error(local_diagnostics.redact(str(error)))
    cost = request.estimated_cost_vnd if request else 0
    st.caption(f"Giá niêm yết tham khảo: {cost:,} VNĐ/clip. Chi phí/quyền sử dụng thực tế do gateway áp dụng theo tài khoản. [Tài liệu và bảng giá](https://api.buihuuthang.com/docs/video)")
    if st.button(f"Tạo 1 clip · khoảng {cost:,}đ",disabled=bool(active) or not present or request is None,type="primary"):
        try:
            if selection is not None:
                save_shot_prompt(project,scene.id,shot_index,prompt)
            st.session_state[state_key] = manager.submit(project,request,settings)
            st.rerun()
        except Exception as error:
            local_diagnostics.record_exception(error,"UI lưu prompt trước khi gửi clip")
            st.error(local_diagnostics.redact(str(error)))
    key = st.session_state.get(state_key) or active
    snapshot = manager.snapshot(key) if key else None
    running = bool(snapshot and snapshot["status"] in {"queued","running"})

    @st.fragment(run_every=1 if running else None)
    def panel():
        value = manager.snapshot(key) if key else None
        if not value:
            return
        st.progress(value["progress"],text=value["message"])
        if value["status"] == "failed":
            st.error(value["error"])
            if debug:
                with st.expander("Traceback đã che key"):
                    st.code(value["traceback"],language="text")
        if running and value["status"] not in {"queued","running"}:
            st.rerun()
    panel()
    folder = confined(project,"ai_video")
    jobs = sorted(folder.glob("*.json"),key=lambda p:p.stat().st_mtime,reverse=True) if folder.exists() else []
    if jobs:
        st.subheader("Job đã lưu")
        selected = st.selectbox("Chọn job",jobs,format_func=lambda path:path.stem[:12])
        try:
            selected = confined(folder,selected.name)
            data = load_job(selected)
            st.write(f"Model: {data['request']['model']} · {data['request']['seconds']} giây · Trạng thái: {data['status']}")
            if data.get("remote_id"):
                st.caption("Job ID: "+local_diagnostics.redact(data["remote_id"]))
            failed_job_details(data,local_diagnostics)
            if data.get("error"):
                st.warning(local_diagnostics.redact(data["error"]))
            if data.get("simpler_prompt_suggestion"):
                st.info(data.get("retry_notice","Đề xuất prompt đơn giản hơn; chưa tự tạo lại job."))
                st.code(data["simpler_prompt_suggestion"],language="text")
                if st.button("Dùng prompt đơn giản cho lần tạo mới",key="simplify_"+selected.stem,disabled=bool(active)):
                    st.session_state[prompt_key+"_pending"] = data["simpler_prompt_suggestion"]
                    st.rerun()
            clip = confined(project,data["clip_path"]) if data.get("clip_path") else None
            if clip and clip.is_file():
                st.video(str(clip))
                st.caption(f"{data.get('width')}×{data.get('height')} · {data.get('duration_sec',0):.2f} giây · {clip.stat().st_size/1024**2:.2f} MB")
                st.download_button("Tải clip AI",clip.read_bytes(),file_name=clip.name,mime="video/mp4")
            elif data.get("remote_id"):
                if st.button("Tiếp tục kiểm tra / tải clip",disabled=bool(active)):
                    st.session_state[state_key] = manager.submit(project,None,settings,job_path=selected)
                    st.rerun()
            else:
                recovery_controls(project,selected,data,settings,disabled=bool(active))
        except Exception as error:
            local_diagnostics.record_exception(error,"UI đọc job AI Video")
            st.error(local_diagnostics.redact(str(error)))
