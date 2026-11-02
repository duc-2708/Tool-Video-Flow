"""Bộ thành phần UI dùng chung theo phong cách Đen - Vàng - Trắng (Black - Gold - White).

An toàn XSS: mọi nội dung chuỗi đầu vào đều được escape bằng html.escape.
"""
from collections.abc import Callable
import html
import streamlit as st


def section_header(eyebrow: str, title: str, accent_word: str = "") -> None:
    """Render tiêu đề phần với eyebrow viết hoa màu vàng và chữ nhấn màu vàng."""
    e_safe = html.escape(eyebrow)
    t_safe = html.escape(title)
    if accent_word:
        a_safe = html.escape(accent_word)
        if a_safe in t_safe:
            t_safe = t_safe.replace(a_safe, f'<span class="text-gold-accent">{a_safe}</span>')
    st.markdown(
        f"""
        <div style="margin-bottom: 20px;">
            <div class="ui-eyebrow">{e_safe}</div>
            <h1 style="margin: 0; font-size: 2.2rem; font-weight: 800; letter-spacing: -0.03em;">{t_safe}</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )


def chip_html(text: str, tone: str = "neutral") -> str:
    """Trả về mã HTML cho một badge/chip bo tròn 999px an toàn."""
    safe_text = html.escape(str(text))
    cls_map = {
        "gold": "ui-chip-gold",
        "green": "ui-chip-green",
        "red": "ui-chip-red",
        "neutral": "ui-chip-neutral",
        "white": "ui-chip-white",
    }
    css_cls = cls_map.get(tone, "ui-chip-neutral")
    return f'<span class="ui-chip {css_cls}">{safe_text}</span>'


def chip(text: str, tone: str = "neutral") -> None:
    """Hiển thị badge/chip trực tiếp trên giao diện."""
    st.markdown(chip_html(text, tone), unsafe_allow_html=True)


def card(title: str, body_fn: Callable[[], None] | None = None, tone: str = "dark") -> None:
    """Card container bo góc 18px với 3 loại tone: dark (bề mặt #141414), white (#FFFFFF), outline."""
    css_class = "ui-card-white" if tone == "white" else "ui-card-outline" if tone == "outline" else "ui-card-dark"
    t_safe = html.escape(title) if title else ""
    with st.container():
        if title:
            header_html = f'<div style="font-weight: 700; font-size: 1.15rem; margin-bottom: 12px;">{t_safe}</div>'
        else:
            header_html = ""
        st.markdown(f'<div class="{css_class}">{header_html}', unsafe_allow_html=True)
        if body_fn:
            body_fn()
        st.markdown("</div>", unsafe_allow_html=True)


def stat_html(label: str, value: str, sub: str = "") -> str:
    """Trả về mã HTML cho ô số liệu thống kê."""
    l_safe = html.escape(str(label))
    v_safe = html.escape(str(value))
    sub_html = f'<div style="font-size: 0.75rem; color: #888888; margin-top: 2px;">{html.escape(str(sub))}</div>' if sub else ""
    return f"""
    <div style="background: #141414; border: 1px solid #2A2A2A; border-radius: 14px; padding: 14px 18px;">
        <div style="font-size: 0.8rem; color: #A8A8A8; font-weight: 600; text-transform: uppercase;">{l_safe}</div>
        <div style="font-size: 1.6rem; color: #FFFFFF; font-weight: 800; margin-top: 4px;">{v_safe}</div>
        {sub_html}
    </div>
    """


def stat(label: str, value: str, sub: str = "") -> None:
    """Hiển thị ô số liệu thống kê trực tiếp."""
    st.markdown(stat_html(label, value, sub), unsafe_allow_html=True)


def stepper_html(steps: list[str], active_index: int, times: list[str] | None = None) -> str:
    """Trả về thanh tiến trình ngang 5 bước: hoàn thành (xong + tick), đang chạy (vàng), chờ (viền)."""
    items = []
    times = times or []
    for idx, s in enumerate(steps):
        s_safe = html.escape(str(s))
        time_safe = f" · {html.escape(times[idx])}" if idx < len(times) and times[idx] else ""
        if idx < active_index:
            items.append(f'<div class="ui-step-item ui-step-done"><span class="check">✓</span> {s_safe}{time_safe}</div>')
        elif idx == active_index:
            items.append(f'<div class="ui-step-item ui-step-active">⚡ {s_safe}</div>')
        else:
            items.append(f'<div class="ui-step-item ui-step-pending">! {s_safe}</div>')
    return f'<div class="ui-stepper">{" ".join(items)}</div>'


def stepper(steps: list[str], active_index: int, times: list[str] | None = None) -> None:
    """Hiển thị thanh tiến trình trực tiếp."""
    st.markdown(stepper_html(steps, active_index, times), unsafe_allow_html=True)


def empty_state(message: str, sub: str = "") -> None:
    """Hiển thị trạng thái rỗng gọn gàng, không dùng emoji."""
    m_safe = html.escape(str(message))
    sub_html = f'<div style="font-size: 0.9rem; color: #888888; margin-top: 6px;">{html.escape(str(sub))}</div>' if sub else ""
    st.markdown(
        f"""
        <div style="text-align: center; padding: 40px 20px; background: #141414; border: 1px dashed #2A2A2A; border-radius: 18px;">
            <div style="font-size: 1.1rem; color: #FFFFFF; font-weight: 600;">{m_safe}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
