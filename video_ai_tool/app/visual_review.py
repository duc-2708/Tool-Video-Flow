"""Local per-shot graphic decisions; no model call and no Assets invalidation."""
import streamlit as st
from agents.visual_planner import assign_visuals,visual_issues
from agents.visual_policy import (background_warnings,load_decisions,save_decision,
    selected_choice,neutral_visual,repair_label_order)


def render_visual_controls(plan,brief,project,diagnostics):
    preview=plan.model_copy(deep=True)
    resolved=project/"edit_plan.resolved.json"
    if resolved.is_file():
        from schemas.assets import ResolvedEditPlan
        try:
            candidate=ResolvedEditPlan.model_validate_json(resolved.read_text(encoding="utf-8"))
            if {s.id:s.narration for s in candidate.scenes}=={s.id:s.narration for s in plan.scenes}:
                preview=candidate
        except Exception as error:
            diagnostics.record_exception(error,"UI đồ họa: dùng Edit Plan gốc thay resolved chưa đọc được")
    assign_visuals(preview,brief)
    ordered=repair_label_order(preview)
    findings=visual_issues(preview,brief)+background_warnings(preview,brief)+ordered
    try: decisions=load_decisions(project)
    except Exception as error:
        diagnostics.record_exception(error,"Đọc lựa chọn đồ họa UI")
        st.warning("Không đọc được lựa chọn đồ họa đã lưu.");decisions={}
    with st.expander("Kiểm tra đồ họa theo từng shot",expanded=bool(findings)):
        st.caption("Lựa chọn lưu riêng trong visual_decisions.json và được Render áp dụng; không gọi API, không thay Assets.")
        for scene in preview.scenes:
            for index,shot in enumerate(scene.shots,1):
                if not shot.visual or shot.visual.template=="stock": continue
                with st.expander(f"Cảnh {scene.id} · Shot {index} · {shot.visual.template}"):
                    st.json(shot.visual.model_dump(mode="json"))
                    for sid,message in findings:
                        if sid==scene.id and message.startswith(f"Shot {index}:"):
                            st.warning(diagnostics.redact(message))
                    choice=selected_choice(decisions,scene,index)
                    if choice: st.caption("Đã chọn: "+("Giữ nguyên (tôi chịu trách nhiệm)" if choice=="keep" else "Dùng bản trung tính"))
                    st.caption("Bản trung tính: "+neutral_visual(scene,shot).data.text)
                    left,right=st.columns(2)
                    for column,label,value in ((left,"Dùng bản trung tính","neutral"),(right,"Giữ nguyên (tôi chịu trách nhiệm)","keep")):
                        if column.button(label,key=f"visual_{project.name}_{scene.id}_{index}_{value}"):
                            try:
                                save_decision(project,scene,index,value)
                                st.rerun()
                            except Exception as error:
                                diagnostics.record_exception(error,"Lưu lựa chọn đồ họa")
                                st.error("Không lưu được lựa chọn: "+diagnostics.redact(str(error)))
