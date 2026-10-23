"""Input coercion for observed style only; essential timestamps stay validated."""
import json
import types
from typing import Annotated,ClassVar,Union,get_args,get_origin
from pydantic import ConfigDict,Field,ValidationError,model_validator
from schemas.base import StrictModel

EMPTY={"","none","null","n/a","na","không có","khong co","không rõ","khong ro","unknown"}


def text(value):
    if isinstance(value,(list,tuple)):
        return "; ".join(text(v) for v in value if v is not None)
    if isinstance(value,dict):
        return json.dumps(value,ensure_ascii=False)
    return str(value)


def base_type(annotation):
    while get_origin(annotation) is Annotated:
        annotation=get_args(annotation)[0]
    if get_origin(annotation) in (Union,types.UnionType):
        annotation=next((v for v in get_args(annotation) if v is not type(None)),annotation)
        return base_type(annotation)
    return annotation


def normalize_observation(cls,value):
    if not isinstance(value,dict):
        if value is None:
            value={}
        elif cls.text_field:
            value={cls.text_field:text(value)}
        else:
            return value
    data=dict(value)
    # Avoid changing caller-owned dictionaries during repeated before-validation.
    data["analysis_warnings"]=list(data.get("analysis_warnings") or []) if isinstance(data.get("analysis_warnings",[]),(list,tuple)) else [text(data["analysis_warnings"])]
    for name,field in cls.model_fields.items():
        if name not in data:
            continue
        val=data[name]
        if val is None and not field.is_required() and type(None) not in get_args(field.annotation):
            data.pop(name);continue
        kind=base_type(field.annotation)
        if kind is str and val is not None:
            data[name]=text(val)
        elif kind in (float,int) and isinstance(val,str):
            try:
                numeric=val.strip().replace(",",".")
                if ":" in numeric and name in {"start_sec","end_sec","duration_sec"}:
                    parts=[float(p) for p in numeric.split(":")]
                    if not 2<=len(parts)<=3: raise ValueError
                    number=sum(p*60**i for i,p in enumerate(reversed(parts)))
                else:
                    number=float(numeric)
                data[name]=int(number) if kind is int and number.is_integer() else number
            except (ValueError,OverflowError):
                if not field.is_required():
                    data.pop(name)
                    data.setdefault("analysis_warnings",[]).append(f"{name}: số không hợp lệ; dùng giá trị mặc định.")
        elif kind is bool:
            if val in (0,1): data[name]=bool(val)
            elif isinstance(val,str) and val.strip().casefold() in {"true","false","yes","no","có","không","1","0"}:
                data[name]=val.strip().casefold() in {"true","yes","có","1"}
        elif get_origin(kind) is list:
            if isinstance(val,str): data[name]=[] if val.strip().casefold() in EMPTY else [val]
            elif isinstance(val,dict): data[name]=[val]
            elif isinstance(val,tuple): data[name]=list(val)
            if base_type(get_args(kind)[0]) is str and isinstance(data.get(name),list):
                data[name]=[text(v) for v in data[name] if v is not None]
            elif base_type(get_args(kind)[0]) in (float,int) and isinstance(data.get(name),list):
                import math
                parsed=[]
                number_type=base_type(get_args(kind)[0])
                for index,item in enumerate(data[name]):
                    try:
                        if isinstance(item,(bool,dict,list)) or item is None: raise ValueError
                        number=float(str(item).strip().replace(",","."))
                        if not math.isfinite(number) or number_type is int and not number.is_integer(): raise ValueError
                        parsed.append(number_type(number))
                    except (ValueError,TypeError,OverflowError):
                        data["analysis_warnings"].append(f"{name}[{index}]: bỏ giá trị số không hợp lệ.")
                data[name]=parsed
        if name not in {"analysis_warnings","normalization_notes"} and name in data and type(data[name]) is not type(val):
            data.setdefault("analysis_warnings",[]).append(f"{name}: chuẩn hóa kiểu {type(val).__name__} → {type(data[name]).__name__}.")
    return data


class StyleObservation(StrictModel):
    # Unknown descriptive metadata is not a reason to discard paid observations.
    model_config=ConfigDict(extra="ignore",allow_inf_nan=False)
    text_field: ClassVar[str|None]=None
    analysis_warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="wrap")
    @classmethod
    def optional_observations(cls,value,handler):
        """Recover optional observations locally; never swallow essential row errors."""
        pending=value
        warnings=[]
        for _ in range(len(cls.model_fields)+1):
            try:
                result=handler(pending)
                result.analysis_warnings=list(dict.fromkeys(result.analysis_warnings+warnings))
                return result
            except ValidationError as error:
                if not isinstance(pending,dict):
                    raise
                replace=set()
                for issue in error.errors(include_input=False,include_url=False):
                    key=issue["loc"][0] if issue["loc"] else None
                    field=cls.model_fields.get(key)
                    if field is None or field.is_required() or key in {"scenes","hook","structure","analysis_warnings"}:
                        raise
                    replace.add(key)
                    warnings.append(f"{key}: {issue['msg']}; dùng giá trị mặc định.")
                pending={k:v for k,v in pending.items() if k not in replace}
        raise ValueError("Không chuẩn hóa được các trường thiết yếu của phân tích.")

    @model_validator(mode="before")
    @classmethod
    def normalize_types(cls,value):
        return normalize_observation(cls,value)
