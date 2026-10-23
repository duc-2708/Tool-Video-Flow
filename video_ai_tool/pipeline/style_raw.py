"""Durable UTF-8 raw responses, local repair and explicit schema diagnostics."""
from pathlib import Path
from pydantic import ValidationError
from schemas.style import StyleAnalysis
from utils.atomic_io import read_json_atomic,write_json_atomic,write_text_atomic
from utils.cache import cache_key
from utils.json_response import parse_json_object,TruncatedJSONError


class StyleRawError(ValueError):
    def __init__(self,message,path,fields=(),*,truncated=False):
        self.raw_path=Path(path);self.fields=list(fields)
        self.truncated=truncated
        super().__init__(message+f" Bản thô: {path}. Chọn 'Sửa lại từ bản thô' hoặc --from-raw; không gọi lại Gemini.")


def raw_path(settings,category,video_hash):
    from pipeline.style_learner import storage
    import re
    if not re.fullmatch(r"[a-f0-9]{64}",video_hash):
        raise ValueError("Hash bản thô phải là SHA256.")
    if category:
        from config.categories import resolve_category
        category=resolve_category(settings,category).category_id
    folder=storage(settings)/(category or "_unsorted")
    path=folder/(video_hash+".raw.txt")
    if folder.is_symlink() or path.is_symlink() or not path.resolve().is_relative_to(storage(settings)):
        raise ValueError("Bản thô phải nằm trong thư viện analysis.")
    return path


class RawResponse:
    def __init__(self,path,identity,diagnostics,*,duration_limit=None):
        self.path=Path(path);self.identity=identity;self.diagnostics=diagnostics
        self.meta=self.path.with_suffix(".meta.json")
        self.revision=0
        self.mode="normal"
        self.compact_retry_used=False
        self.duration_limit=duration_limit

    def metadata(self):
        try:
            return read_json_atomic(self.meta) if self.meta.exists() else {}
        except (OSError,ValueError) as error:
            self.diagnostics.record_exception(error,"Metadata bản thô lỗi; giữ raw và chỉ thử parse tại máy")
            return {}

    def save(self,text,status=None):
        text=self.diagnostics.redact(text)
        if self.path.exists():
            previous=self.path.read_text(encoding="utf-8")
            if previous!=text:
                archive=self.path.with_name(self.path.name.replace(".raw.txt","."+cache_key(previous)[:12]+".raw.txt"))
                write_text_atomic(archive,previous)
                previous_meta=self.metadata()
                if previous_meta:
                    write_json_atomic(archive.with_suffix(".meta.json"),previous_meta)
        # Publish the paid output before any JSON parsing/schema validation.
        write_text_atomic(self.path,text)
        if self.path.read_text(encoding="utf-8")!=text:
            raise OSError("Không xác nhận được bản thô đã lưu; chưa parse kết quả Gemini.")
        status=dict(status or {})
        status.update(mode=self.mode,compact_retry_used=self.compact_retry_used)
        truncated=bool(status.get("truncated") or "MAX_TOKENS" in status.get("finish_reasons",[]))
        status["truncated"]=truncated
        write_json_atomic(self.meta,{"identity":self.identity,"raw_hash":cache_key(text),"status":status,"truncated":truncated,
            "compact_retry_used":self.compact_retry_used})
        self.revision+=1

    def is_truncated(self):
        metadata=self.metadata();status=metadata.get("status",{})
        if status.get("blocked"):
            return False
        if self.path.exists() and metadata.get("raw_hash") and metadata["raw_hash"]!=cache_key(self.path.read_text(encoding="utf-8")):
            return False  # A manually edited raw must first be parsed locally.
        return bool(metadata.get("truncated") or status.get("truncated") or "MAX_TOKENS" in status.get("finish_reasons",[]))

    def mark_truncated(self,reason):
        metadata=self.metadata()
        metadata.setdefault("identity",self.identity)
        metadata["raw_hash"]=cache_key(self.path.read_text(encoding="utf-8"))
        metadata["truncated"]=True
        status=metadata.setdefault("status",{})
        status.update(truncated=True,truncation_reason=reason)
        write_json_atomic(self.meta,metadata)

    def retry_exhausted(self):
        metadata=self.metadata()
        return bool(metadata.get("compact_retry_used") or metadata.get("status",{}).get("compact_retry_used"))

    def parse(self):
        text=self.path.read_text(encoding="utf-8")
        metadata=self.metadata();status=metadata.get("status",{})
        if status.get("blocked"):
            raise StyleRawError("Gemini chặn phản hồi vì an toàn; không đưa vào hồ sơ.",self.path)
        try:
            data=parse_json_object(text)
            video=status.get("video",{})
            limit=self.duration_limit or video.get("analyzed_end_sec") or video.get("analysis_duration_sec") or video.get("duration_sec")
            context={"duration_limit":limit}
            analysis=StyleAnalysis.model_validate(data,context=context)
            if status.get("mode")=="compact":
                from schemas.style_compact import CompactStyleAnalysis
                # Repair optional metadata/timestamps before the compact projection, too.
                data=CompactStyleAnalysis.model_validate(analysis.model_dump(mode="json")).model_dump(mode="json")
                data["analysis_warnings"]=analysis.analysis_warnings
                analysis=StyleAnalysis.model_validate(data,context=context)
            if not analysis.scenes:
                raise ValueError("scenes: cần bảng cảnh chi tiết; bổ sung từ video vào bản thô.")
            return analysis
        except TruncatedJSONError as error:
            self.mark_truncated("unbalanced_json")
            raise StyleRawError(str(error),self.path,truncated=True) from None
        except ValidationError as error:
            fields=[{"field":".".join(str(p) for p in e["loc"]) or "analysis","message":e["msg"],"type":e["type"]}
                for e in error.errors(include_input=False,include_url=False)]
            details="; ".join(e["field"]+": "+e["message"] for e in fields)
            raise StyleRawError("Các trường phân tích chưa hợp lệ: "+details,self.path,fields) from None
        except ValueError as error:
            raise StyleRawError(str(error),self.path) from None


def reuse_raw(store,*,offline=False,force=False):
    """Existing paid raw always wins; even force/relearn never overwrites it."""
    if not store.path.exists():
        if offline:
            raise ValueError("Chưa có bản thô cho video này; --from-raw không gọi Gemini.")
        return None
    analysis=store.parse()
    if store.is_truncated():
        raise StyleRawError("truncated=true: giữ nguyên bản thô đã có, không tự gọi lại Gemini; sửa bản thô tại máy.",store.path,truncated=True)
    return analysis
