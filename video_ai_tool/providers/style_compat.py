"""One controlled HTTP-400 bisect; remember only accepted configurations."""
import json
from importlib.metadata import version
from utils.atomic_io import read_json_atomic,write_json_atomic,write_text_atomic
from utils.cache import cache_key
from utils.file_lock import file_lock
from providers.style_schema import flat_style_schema


class StyleCompatibility:
    def __init__(self,settings,diagnostics,model):
        self.settings=settings;self.diagnostics=diagnostics
        self.path=settings.cache_dir/"style_compatibility.json"
        self.key=cache_key([model,version("google-genai"),settings.style_media_resolution,settings.style_use_response_schema,
            settings.style_max_output_tokens,settings.style_schema_mode,settings.style_compact_output,1])
        self.options={"media_resolution":None if settings.style_media_resolution=="none" else settings.style_media_resolution,
            "use_schema":settings.style_use_response_schema,"max_output_tokens":settings.style_max_output_tokens,
            "schema_mode":settings.style_schema_mode,"compact":settings.style_compact_output}
        try:
            row=read_json_atomic(self.path).get(self.key,{})
            if row.get("accepted") and self.valid(row.get("options")):
                self.options=row["options"]
        except (OSError,ValueError): pass

    @staticmethod
    def valid(value):
        return isinstance(value,dict) and set(value)=={"media_resolution","use_schema","max_output_tokens","schema_mode","compact"} and value["media_resolution"] in {None,"low","medium"} and type(value["use_schema"]) is bool and type(value["compact"]) is bool and type(value["max_output_tokens"]) is int and 1024<=value["max_output_tokens"]<=65536 and value["schema_mode"] in {"flat","essential"}

    def candidates(self):
        current=dict(self.options)
        yield "initial",dict(current)
        for label,change in (("a:no_media_resolution",{"media_resolution":None}),
                ("b:json_without_schema",{"use_schema":False}),
                ("c:compact_8192",{"max_output_tokens":8192,"compact":True}),
                ("d:essential_flat_schema",{"use_schema":True,"schema_mode":"essential","compact":True})):
            updated={**current,**change}
            if updated!=current:
                current=updated;yield label,dict(current)

    def remember(self,options):
        self.options={k:v for k,v in options.items() if k in self.options}
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            with file_lock(self.path.with_suffix(".lock"),timeout=3):
                try: data=read_json_atomic(self.path)
                except (OSError,ValueError): data={}
                data[self.key]={"accepted":True,"options":self.options}
                write_json_atomic(self.path,data)
            p=self.options
            suggested=(f"STYLE_USE_RESPONSE_SCHEMA={str(p['use_schema']).lower()}\n"
                f"STYLE_MEDIA_RESOLUTION={p['media_resolution'] or 'none'}\nSTYLE_MAX_OUTPUT_TOKENS={p['max_output_tokens']}\n"
                f"STYLE_SCHEMA_MODE={p['schema_mode']}\nSTYLE_COMPACT_OUTPUT={str(p['compact']).lower()}\n")
            write_text_atomic(self.settings.logs_dir/"style_compatibility.suggested.env",suggested)
        except (OSError,TimeoutError) as error:
            self.diagnostics.record_exception(error,"Đã có cấu hình Style chạy được trong bộ nhớ nhưng chưa lưu được gợi ý/cache")

    def generate(self,llm,media,prompt,schema,compact_prompt,progress,raw_store):
        from providers.llm_gemini import GeminiRequestError
        from schemas.style_compact import CompactStyleAnalysis
        for label,profile in self.candidates():
            compact=profile["compact"] or raw_store.mode=="compact"
            selected=CompactStyleAnalysis if compact else schema
            wire=flat_style_schema(selected,essential=profile["schema_mode"]=="essential")
            actual_prompt=compact_prompt(prompt) if compact else prompt
            if not profile["use_schema"]:
                actual_prompt+="\nChỉ trả JSON thuần; trường không quan sát được hãy bỏ qua. Schema tham khảo:\n"+json.dumps(wire,ensure_ascii=False)
            else:
                actual_prompt+="\nSchema gửi đi chỉ dùng kiểu cụ thể: trường phụ không có dữ liệu hãy BỎ TRƯỜNG, không trả null. Cảnh cuối bỏ transition_to_next; Pydantic sẽ đặt None tại máy."
            raw_store.mode="compact" if compact else "normal"
            llm.media_request_options={**profile,"wire_schema":wire}
            self.diagnostics.record(f"Style bisect={label}: "+json.dumps(profile,ensure_ascii=False))
            try:
                value=llm.generate_media_json(actual_prompt,media,selected)
            except GeminiRequestError as error:
                if error.code!=400: raise
                detail=self.diagnostics.redact(str(error))
                progress("Gemini 400 INVALID_ARGUMENT — lỗi cấu hình/request, không đánh dấu video hỏng. "+detail)
                last=error
                continue
            self.remember(profile)
            if label!="initial": progress("Cấu hình Style hoạt động: "+json.dumps(profile,ensure_ascii=False)+"; đã lưu gợi ý, dùng cho video tiếp theo.")
            return value
        raise GeminiRequestError(400,"Gemini từ chối cấu hình/request sau các bước khoanh vùng 400; không kết luận video hỏng. "+str(last)) from last
