"""Offline raw response repair; this action never authorizes an API request."""
import streamlit as st
from pathlib import Path
from pipeline.style_raw import RawResponse,StyleRawError
from utils.cache import cache_key


def render(settings,items,manager,active,scope,diagnostics):
    for item in items:
        if not item.get("raw_path"):
            continue
        path=settings.root_dir/item["raw_path"]
        from pipeline.style_learner import storage
        if path.is_symlink() or not path.resolve().is_relative_to(storage(settings)):
            st.error("Đường dẫn bản thô nằm ngoài thư viện.")
            continue
        with st.expander(item["filename"]+" · Sửa lại từ bản thô (không gọi Gemini)"):
            try:
                store=RawResponse(path,{},diagnostics)
                text=path.read_text(encoding="utf-8")
                metadata=store.metadata()
                blocked=metadata.get("status",{}).get("blocked",False)
                if store.is_truncated():
                    st.warning("truncated=true: bản thô bị cắt. Giữ nguyên dữ liệu đã có, không tự gọi lại Gemini; sửa JSON tại đây để parse lại tại máy.")
                try:
                    store.parse()
                    st.caption("Bản thô parse/validate được; có thể lưu lại kết quả tại máy.")
                except StyleRawError as error:
                    st.error(diagnostics.redact(str(error)))
                    if error.fields:
                        st.dataframe(error.fields,hide_index=True,width="stretch")
                edited=st.text_area("Phản hồi thô UTF-8 — sửa JSON/trường sai tại đây",value=text,height=260,key="style_raw_editor_"+scope+cache_key([item["filename"],text]))
                st.download_button("Tải phản hồi thô",data=text.encode("utf-8"),file_name=path.name,mime="text/plain; charset=utf-8",key="style_raw_download_"+cache_key(item["filename"]))
                if st.button("Sửa lại từ bản thô",disabled=bool(active) or blocked,key="style_raw_repair_"+cache_key(item["filename"])):
                    if edited!=text:
                        store.identity=metadata.get("identity",{})
                        store.save(edited,{"manually_edited":True})
                    st.session_state["style_worker"]=manager.submit_analysis([item["filename"]],settings,from_raw=True)
                    st.rerun()
            except (OSError,ValueError) as error:
                st.error(diagnostics.redact(str(error)))
