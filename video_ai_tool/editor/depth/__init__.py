"""Bundle 3D Depth Engine (CSS 3D & Isometric Perspective layers)."""
import hashlib
from pathlib import Path

FOLDER = Path(__file__).resolve().parent / "engine"


def bundle_depth():
    """Return (css_str, js_str, sha256_digest) for Depth 3D Engine."""
    js_parts = []
    hasher = hashlib.sha256()

    js_files = ["depth.js"]
    for name in js_files:
        path = FOLDER / name
        if path.is_file():
            content = path.read_text(encoding="utf-8")
            js_parts.append(content)
            hasher.update(path.read_bytes())

    css_path = FOLDER / "depth.css"
    css_str = ""
    if css_path.is_file():
        css_str = css_path.read_text(encoding="utf-8")
        hasher.update(css_path.read_bytes())

    js_str = "\n".join(js_parts)
    return css_str, js_str, hasher.hexdigest()
