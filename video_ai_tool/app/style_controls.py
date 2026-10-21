"""One preset selector shared by all pipeline entry forms."""
import streamlit as st
from pipeline.style_profile import list_profiles


def select_style(settings, *, key, current=None):
    profiles = list_profiles(settings)
    names = {p.slug: p.name for p in profiles}
    options = [None, *names]
    return st.selectbox("Phong cách mẫu", options, index=options.index(current) if current in options else 0,
                        format_func=lambda value: names.get(value, "Không dùng"), key=key)
