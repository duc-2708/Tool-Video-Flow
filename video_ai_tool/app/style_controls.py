"""One preset selector shared by all pipeline entry forms."""
import streamlit as st
from pipeline.style_profile import list_profiles
from config.categories import categories_for,resolve_category


def select_category(settings,*,key,current=None):
    categories=[c for c in categories_for(settings).categories if c.enabled]
    names={c.category_id:c.name for c in categories}
    options=[None,*names]
    if current:
        current=resolve_category(settings,current).category_id
    if st.session_state.get(key) not in options:
        st.session_state[key]=current if current in options else None
    return st.selectbox("Danh mục",options,index=options.index(current) if current in options else 0,
        format_func=lambda value:names.get(value,"— Không chọn danh mục —"),key=key)


def select_style(settings, *, key, current=None,category=None,video_type=None):
    profiles = list_profiles(settings)
    names = {p.slug: p.name for p in profiles}
    automatic=None
    context=(category,video_type)
    if category:
        from pipeline.category_style import resolve_profile
        profile,automatic,notices=resolve_profile(settings,category,video_type)
        names[automatic]="Tự động · "+profile.name
        names["@default"]="Hồ sơ mặc định chung"
        for notice in notices:
            st.info(notice)
        st.caption(f"Hồ sơ: {profile.video_count} video · độ tin cậy {profile.confidence_label}")
    if current and current.startswith("@") and current not in names:
        from pipeline.style_profile import load_profile
        names[current]=load_profile(settings,current).name
    options = [None, *names]
    old_auto=st.session_state.get(key+"_auto")
    changed=st.session_state.get(key+"_context")!=context
    if changed or st.session_state.get(key) not in options or old_auto and st.session_state.get(key)==old_auto and old_auto!=automatic:
        st.session_state[key]=current if current in options and current is not None else None if current=="none" else automatic
    st.session_state[key+"_context"]=context
    st.session_state[key+"_auto"]=automatic
    selected=st.selectbox("Phong cách mẫu", options,format_func=lambda value: names.get(value, "Không dùng"), key=key)
    return "none" if selected is None and category else selected


def selection_for_type(settings,category,video_type,selection,auto_value):
    if category and selection==auto_value:
        from pipeline.category_style import resolve_profile
        return resolve_profile(settings,category,video_type)[1]
    return selection
