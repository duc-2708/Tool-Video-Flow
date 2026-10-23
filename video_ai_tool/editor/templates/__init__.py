"""Public registry; each module exposes render(data,duration,size,theme)."""
from editor.templates.core import NAMES, render_template
from editor.templates.theme import load_theme


def render(name,data,duration,size,theme=None):
    return render_template(name,data,duration,size,theme)
