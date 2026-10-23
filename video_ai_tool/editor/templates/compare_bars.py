from editor.templates.core import render_template


def render(data, duration, size, theme=None):
    return render_template("compare_bars", data, duration, size, theme)
