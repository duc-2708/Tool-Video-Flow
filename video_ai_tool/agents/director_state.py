"""Durable, project-local Director checkpoints; checked inputs determine reuse."""
from datetime import datetime,timezone
from pathlib import Path
from pydantic import ValidationError
from utils.atomic_io import read_json_atomic,write_json_atomic
from utils.cache import cache_key


class DirectorState:
    def __init__(self,path,inputs,diagnostics,progress):
        self.path=Path(path);self.diagnostics=diagnostics;self.progress=progress
        fingerprint=cache_key(inputs)
        self.data={"version":1,"input_hash":fingerprint,"stages":{}}
        if self.path.exists():
            try:
                previous=read_json_atomic(self.path)
                if previous.get("version")==1 and previous.get("input_hash")==fingerprint and isinstance(previous.get("stages"),dict):
                    self.data=previous
                else: diagnostics.record("Director checkpoint khác brief/cấu hình/prompt; không dùng lại các lượt cũ.")
            except (OSError,ValueError) as error:
                diagnostics.record_exception(error,"Director checkpoint lỗi; chỉ dùng lại dữ liệu đọc/validate được")

    def load(self,stage,schema):
        row=self.data["stages"].get(stage,{})
        if row.get("status")!="done": return None
        try:
            if cache_key(row["data"])!=row["hash"]: raise ValueError("Checkpoint hash không khớp.")
            value=schema.model_validate(row["data"])
        except (KeyError,TypeError,ValueError,ValidationError) as error:
            self.diagnostics.record_exception(error,f"Director checkpoint {stage} chưa hợp lệ; chạy lại từ lượt này")
            self.invalidate_from(stage)
            return None
        self.progress(f"Tiếp tục Director: dùng lượt {stage} đã lưu, không gọi lại Gemini.")
        return value

    def invalidate_from(self,stage):
        order=["outline","written","humanized","final"]
        for key in order[order.index(stage):]: self.data["stages"].pop(key,None)
        self._write()

    def save(self,stage,value):
        data=value.model_dump(mode="json")
        self.data["stages"][stage]={"status":"done","data":data,"hash":cache_key(data),"completed_at":datetime.now(timezone.utc).isoformat()}
        self.data.pop("error",None)
        self.data["current_stage"]=stage
        self._write()

    def failed(self,stage,error):
        self.data["current_stage"]=stage
        self.data["error"]={"stage":stage,"message":self.diagnostics.redact(str(error)),"at":datetime.now(timezone.utc).isoformat()}
        self._write()

    def _write(self):
        write_json_atomic(self.path,self.data)
