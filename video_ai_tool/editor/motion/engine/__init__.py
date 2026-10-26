"""Bundle Motion Engine 4b JavaScript modules and CSS styling."""
import hashlib
from pathlib import Path

FOLDER = Path(__file__).resolve().parent

ENGINE_JS_FILES = [
    "prng.js",
    "easing.js",
    "path.js",
    "particles.js",
    "camera.js",
    "layout.js",
    "mascot.js",
    "illustrations.js",
    "recipes.js",
    "timeline.js",
]


def bundle_engine():
    """Return (css_str, js_str, sha256_digest) for Motion Engine."""
    js_parts = []
    hasher = hashlib.sha256()

    for name in ENGINE_JS_FILES:
        path = FOLDER / name
        if path.is_file():
            content = path.read_text(encoding="utf-8")
            js_parts.append(content)
            hasher.update(path.read_bytes())

    css_path = FOLDER / "engine.css"
    css_str = ""
    if css_path.is_file():
        css_str = css_path.read_text(encoding="utf-8")
        hasher.update(css_path.read_bytes())

    js_str = "\n".join(js_parts)
    return css_str, js_str, hasher.hexdigest()
