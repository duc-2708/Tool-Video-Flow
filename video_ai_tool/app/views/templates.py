"""Local template sandbox; rendering runs in a background thread."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import importlib
import json
import uuid
import streamlit as st
from editor.templates import NAMES,load_theme
from schemas.visual import VisualData

SAMPLES={
    "hook_card":{"text":"Điều gì đang thay đổi?","highlight":["thay","đổi?"]},
    "stat_card":{"value":5000,"label":"Dữ liệu minh họa mẫu","source":"Nguồn minh họa"},
    "steps_list":{"items":["Xác định mục tiêu","Kiểm tra nguồn","Chọn ý chính","Dựng video"]},
    "compare_bars":{"bars":[{"label":"Minh họa A","value":30,"unit":"%"},{"label":"Minh họa B","value":75,"unit":"%"}]},
    "source_card":{"source":"Nguồn minh họa","date":"Ngày minh họa","title":"Thẻ nguồn đặt ở đầu hoặc cuối video"},
    "text_focus":{"text":"Câu chuyện nằm sau con số","highlight":["câu","chuyện"]}}


@st.cache_resource
def executor(): return ThreadPoolExecutor(max_workers=1,thread_name_prefix="template-preview")


def export(name,data,duration,size,theme,path):
    clip=importlib.import_module("editor.templates."+name).render(data,duration,size,theme)
    try:
        clip.write_videofile(str(path),fps=15,codec="libx264",audio=False,preset="ultrafast",pixel_format="yuv420p",ffmpeg_params=["-movflags","+faststart"],logger=None,threads=2)
    finally: clip.close()
    return path


def render(settings,project,topic,debug,diagnostics):
    st.header("Xem trước mẫu")
    st.caption("Dữ liệu thử chỉ dùng xem mẫu, không đưa vào fact hay video của project. Không gọi API.")
    name=st.selectbox("Mẫu đồ họa",NAMES)
    theme=st.selectbox("Theme",["studio","paper"])
    portrait=st.selectbox("Khổ",["tiktok","youtube"])=="tiktok"
    duration=st.slider("Thời lượng mẫu (giây)",2,12,5)
    raw=st.text_area("Dữ liệu JSON thử",json.dumps(SAMPLES[name],ensure_ascii=False,indent=2),height=240,key="template_data_"+name)
    future=st.session_state.get("template_future")
    if st.button("Xem hoạt ảnh mẫu",disabled=bool(future and not future.done())):
        try:
            data=VisualData.model_validate(json.loads(raw)).model_dump(mode="json")
            folder=settings.output_dir/"template_previews";folder.mkdir(parents=True,exist_ok=True)
            path=folder/f"{name}_{uuid.uuid4().hex[:8]}.mp4"
            st.session_state["template_future"]=executor().submit(export,name,data,duration,(540,960) if portrait else (960,540),load_theme(theme,settings.root_dir),path)
            st.rerun()
        except Exception as error: st.error("Dữ liệu mẫu không hợp lệ: "+diagnostics.redact(str(error)))
    @st.fragment(run_every=1 if future and not future.done() else None)
    def result():
        if not future: return
        if not future.done(): st.info("Đang dựng hoạt ảnh mẫu trong nền…");return
        try:
            path=future.result()
            st.video(str(path))
            st.download_button("Tải mẫu MP4",path.read_bytes(),file_name=path.name,mime="video/mp4")
        except Exception as error:
            diagnostics.record_exception(error,"Xem trước mẫu")
            st.error("Không dựng được mẫu: "+diagnostics.redact(str(error)))
    result()
