"""Loss-tolerant observations: repair timestamps without inventing scene content."""
import math
import re
import unicodedata
from statistics import mean
from pydantic import ValidationError
from schemas.style_normalize import text


def color_hex(value):
    if value is None:
        return None
    value=text(value).strip()
    if re.fullmatch(r"#[a-fA-F0-9]{3}",value):
        return "#"+"".join(c*2 for c in value[1:]).upper()
    if re.fullmatch(r"#[a-fA-F0-9]{6}",value):
        return value.upper()
    folded="".join(c for c in unicodedata.normalize("NFD",value.casefold()) if not unicodedata.combining(c)).replace("đ","d")
    colors=(("xanh duong|xanh da troi|blue","#0000FF"),("xanh la|xanh luc|green","#008000"),
            ("vang|yellow|gold|lemon","#FFFF00"),("trang|white","#FFFFFF"),("den|black","#000000"),
            ("do|red","#FF0000"),("cam|orange","#FFA500"),("hong|pink","#FFC0CB"),
            ("tim|purple|violet","#800080"),("xam|ghi|gray|grey","#808080"),
            ("nau|brown","#A52A2A"),("cyan|turquoise","#00FFFF"),("xanh|teal","#0000FF"))
    return next((code for pattern,code in colors if re.search(r"\b(?:"+pattern+r")\b",folded)),None)


def seconds(value):
    try:
        if isinstance(value,bool): return None
        parts=[float(p) for p in str(value).strip().replace(",",".").split(":")]
        if not 1<=len(parts)<=3: return None
        result=sum(p*60**i for i,p in enumerate(reversed(parts)))
        return result if math.isfinite(result) else None
    except (TypeError,ValueError):
        return None


def repair_timeline(rows,limit,model,label,warnings):
    if not isinstance(rows,list):
        rows=[rows] if isinstance(rows,dict) else []
    candidates=[]
    for index,row in enumerate(rows):
        if hasattr(row,"model_dump"): row=row.model_dump()
        if not isinstance(row,dict):
            warnings.append(f"{label}[{index}]: loại mục không có mốc thời gian.");continue
        row=dict(row)
        start=seconds(row.get("start_sec"));end=seconds(row.get("end_sec"))
        if start is None or start<0 or limit is not None and start>=limit:
            warnings.append(f"{label}[{index}]: loại mốc bắt đầu {row.get('start_sec')!s} ngoài phạm vi/không hợp lệ.");continue
        row["start_sec"]=start;row["end_sec"]=end
        candidates.append((index,row))
    ordered=sorted(candidates,key=lambda pair:pair[1]["start_sec"])
    if ordered!=candidates:
        warnings.append(f"{label}: sắp xếp lại theo start_sec.")
    positive=[r["end_sec"]-r["start_sec"] for _,r in ordered if r["end_sec"] is not None and r["end_sec"]>r["start_sec"]]
    average=mean(positive) if positive else None
    result=[]
    for offset,(index,row) in enumerate(ordered):
        start=row["start_sec"];end=row["end_sec"]
        next_start=next((r["start_sec"] for _,r in ordered[offset+1:] if r["start_sec"]>start),None)
        if result and start<=result[-1].start_sec:
            warnings.append(f"{label}[{index}]: loại mốc bắt đầu trùng {start:g}s.");continue
        if end is None or end<=start:
            repaired=next_start if next_start is not None else start+average if average is not None else None
            if repaired is None:
                warnings.append(f"{label}[{index}]: loại cảnh vì không suy ra được end_sec sau {start:g}s.");continue
            warnings.append(f"{label}[{index}]: sửa end_sec {end} → {repaired:g}s theo cảnh kế/độ dài trung bình.")
            end=repaired
        if limit is not None and end>limit:
            warnings.append(f"{label}[{index}]: cắt end_sec {end:g}s → {limit:g}s theo phạm vi video.")
            end=limit
        if next_start is not None and end>next_start:
            warnings.append(f"{label}[{index}]: cắt phần chồng lấn tại {next_start:g}s.")
            end=next_start
        row["end_sec"]=end
        try:
            result.append(model.model_validate(row))
        except ValidationError as error:
            fields=", ".join(".".join(map(str,e["loc"])) or "mốc thời gian" for e in error.errors(include_input=False))
            warnings.append(f"{label}[{index}]: loại mục không sửa được trường thiết yếu ({fields}).")
    return result


def collect_warnings(value,prefix=""):
    """Keep full field paths for diagnostics, including nested optional models."""
    result=[]
    if hasattr(type(value),"model_fields") and hasattr(value,"analysis_warnings"):
        result.extend(prefix+w for w in value.analysis_warnings)
        for name in type(value).model_fields:
            if name in {"analysis_warnings","normalization_notes"}: continue
            result.extend(collect_warnings(getattr(value,name),prefix+name+"."))
    elif isinstance(value,list):
        for i,item in enumerate(value): result.extend(collect_warnings(item,prefix+str(i)+"."))
    return result
