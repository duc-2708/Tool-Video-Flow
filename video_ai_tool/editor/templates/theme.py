"""Deterministic raster backgrounds, restricted to local assets."""
from functools import lru_cache
from pathlib import Path
import numpy as np
import yaml
from PIL import Image, ImageColor, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = dict(top="#101F32", bottom="#263E55", card="#172D43", foreground="#F8F7F2",
               muted="#ADC1CD", accent="#FFCE52", secondary="#61D7C3", radius=28, shadow=.35, background="gradient")


def load_theme(name="studio", root=None):
    root = Path(root or ROOT)
    path = root/"config/themes.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
    result = {**DEFAULT, **(data or {}).get("themes", {}).get(name, {})}
    from editor.captions import find_font
    result["font"] = str(find_font(root))
    result["root"] = str(root)
    return result


@lru_cache(maxsize=12)
def _background(size, top, bottom, kind):
    w,h = size
    a,b = np.array(ImageColor.getrgb(top)), np.array(ImageColor.getrgb(bottom))
    y = np.linspace(0,1,h)[:,None,None]
    pixels = np.broadcast_to(a*(1-y)+b*y,(h,w,3)).copy()
    if kind == "paper":
        # Low-amplitude seeded creases/noise; no external image dependency.
        noise = np.random.default_rng(17).normal(0,1.5,(h,w,1))
        crease = 2*np.sin(np.arange(w)[None,:,None]/39+np.arange(h)[:,None,None]/87)
        pixels += noise+crease
    return Image.fromarray(np.clip(pixels,0,255).astype("uint8")).convert("RGBA")


def background(size, theme):
    base = _background(tuple(size),theme["top"],theme["bottom"],theme.get("background","gradient")).copy()
    image = theme.get("image","")
    if image:
        folder = Path(theme.get("root",ROOT))/"assets/backgrounds"
        path = (folder/image).resolve()
        if path.is_relative_to(folder.resolve()) and path.is_file():
            try:
                from editor.effects import cover
                with Image.open(path) as source:
                    base=Image.fromarray(cover(np.asarray(source.convert("RGB")),size)).convert("RGBA")
                base=base.filter(ImageFilter.GaussianBlur(3))
            except (OSError,ValueError): pass
    return base
