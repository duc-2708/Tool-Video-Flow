"""Local category palettes and restricted, original SVG mascot states."""
import base64
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import yaml
from PIL import ImageColor

DEFAULT=dict(top="#101b30",bottom="#080c17",card="#16263b",foreground="#f4f7ff",accent="#ffd052",secondary="#61d7c3")


def contrast(a,b):
    def luminance(colour):
        rgb=[v/255 for v in ImageColor.getrgb(colour)[:3]]
        return sum(c*(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4) for c,v in zip((.2126,.7152,.0722),rgb))
    x,y=sorted((luminance(a),luminance(b)))
    return (y+.05)/(x+.05)


def theme_names(root):
    path=Path(root)/"config/motion_theme.yaml"
    try: return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("themes",{})
    except (OSError,ValueError,yaml.YAMLError): return {}


def load_motion_theme(root,plan=None,name="auto"):
    themes=theme_names(root)
    profile=getattr(plan,"style_profile",None)
    if name=="auto":
        v_theme = None
        if plan and getattr(plan, "scenes", None):
            for sc in plan.scenes:
                vp = getattr(sc, "visual_plan", None)
                if vp and getattr(vp, "theme", None) and getattr(vp, "theme") in themes:
                    v_theme = getattr(vp, "theme")
                    break
        name=v_theme or getattr(profile,"category_id",None) or "studio"
    result={**DEFAULT,**themes.get(name,{})};result["name"]=name if name in themes else "studio"
    warnings=[]
    for key,default in DEFAULT.items():
        try:
            if not re.fullmatch(r"#[0-9a-fA-F]{6}",result[key]): raise ValueError
            ImageColor.getrgb(result[key])
        except (TypeError,ValueError): result[key]=default;warnings.append(f"motion_theme nhóm 2: sửa màu {key} không hợp lệ.")
    for key in ("foreground","accent","secondary"):
        if contrast(result[key],result["card"])<4.5:
            result[key]=max(("#ffffff","#000000"),key=lambda c:contrast(c,result["card"]));warnings.append(f"motion_contrast nhóm 2: tăng tương phản {key}.")
    result["warnings"]=warnings
    return result


def mascot_uris(root,states=None):
    result={}
    allowed={"svg","g","path","circle","ellipse","rect","line","polyline","polygon","title","desc"}
    for state in states or ("idle","point","surprised","thinking"):
        path=Path(root)/"assets/mascot"/(state+".svg")
        try:
            raw=path.read_text(encoding="utf-8")
            if len(raw)>100000: continue
            tree=ET.fromstring(raw)
            if any(el.tag.split("}")[-1] not in allowed or any(k.lower().startswith("on") or k.split("}")[-1] in {"href","style"} or "url(" in v.lower() for k,v in el.attrib.items()) for el in tree.iter()): continue
            result[state]="data:image/svg+xml;base64,"+base64.b64encode(raw.encode("utf-8")).decode("ascii")
        except (OSError,ValueError,ET.ParseError): pass
    return result
