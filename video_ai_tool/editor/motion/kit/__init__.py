"""Motion Kit v2 - Pure Seek-Based Deterministic Motion Graphics System."""
from __future__ import annotations

import base64
from functools import lru_cache
import hashlib
from pathlib import Path

KIT_DIR = Path(__file__).resolve().parent
ROOT_DIR = KIT_DIR.parents[2]
FONTS_DIR = ROOT_DIR / "assets" / "fonts"


@lru_cache(maxsize=1)
def get_inter_font_faces() -> str:
    """Load Inter font faces offline from assets/fonts."""
    faces = []
    weight_map = {
        "Inter-Regular.ttf": 400,
        "Inter-SemiBold.ttf": 600,
        "Inter-Bold.ttf": 700,
        "Inter-Black.ttf": 900,
    }
    for filename, weight in weight_map.items():
        fpath = FONTS_DIR / filename
        if fpath.is_file():
            b64 = base64.b64encode(fpath.read_bytes()).decode("ascii")
            faces.append(
                f"@font-face {{\n"
                f"  font-family: 'Inter';\n"
                f"  font-style: normal;\n"
                f"  font-weight: {weight};\n"
                f"  font-display: swap;\n"
                f"  src: url('data:font/truetype;base64,{b64}') format('truetype');\n"
                f"}}"
            )
    return "\n".join(faces)


def bundle_kit() -> tuple[str, str, str]:
    """Bundle Motion Kit v2 CSS, components, and runtime JS.
    
    Returns:
        (css_str, js_str, sha256_hash)
    """
    css_parts = [get_inter_font_faces()]
    kit_css_path = KIT_DIR / "kit.css"
    if kit_css_path.is_file():
        css_parts.append(kit_css_path.read_text(encoding="utf-8"))

    js_parts = []
    components_dir = KIT_DIR / "components"
    for comp in sorted(components_dir.glob("*.js")):
        js_parts.append(comp.read_text(encoding="utf-8"))

    kit_js_path = KIT_DIR / "kit.js"
    if kit_js_path.is_file():
        js_parts.append(kit_js_path.read_text(encoding="utf-8"))

    full_css = "\n".join(css_parts)
    full_js = "\n".join(js_parts)
    digest = hashlib.sha256((full_css + full_js).encode("utf-8")).hexdigest()

    return full_css, full_js, digest


__all__ = ["bundle_kit", "get_inter_font_faces"]
