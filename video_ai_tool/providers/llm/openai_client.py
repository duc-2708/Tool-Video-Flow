"""Official Responses SDK: parsed JSON, bounded retries, local RPM, no stored response."""
from copy import deepcopy
import json
import random
import time
from pydantic import BaseModel
from providers.llm.base import LLMClient, OutputError, TransientError, normalize_error
from utils.diagnostics import Diagnostics
from utils.json_response import parse_json_object
from utils.rate_limit import RateLimiter


def response_format(schema):
    from openai.lib._pydantic import to_strict_json_schema, _ensure_strict_json_schema
    if schema is None: return {"type":"json_object"},None
    original=schema.model_json_schema() if isinstance(schema,type) and issubclass(schema,BaseModel) else deepcopy(schema)
    def free_maps(node):
        if isinstance(node,dict):
            return node.get("additionalProperties") not in (None,False) or node.get("type")=="object" and "properties" not in node or any(free_maps(v) for v in node.values())
        return isinstance(node,list) and any(free_maps(v) for v in node)
    if free_maps(original): return {"type":"json_object"},original
    wire=to_strict_json_schema(schema) if isinstance(schema,type) else _ensure_strict_json_schema(deepcopy(original),path=(),root=deepcopy(original))
    def transport_constraints(node):
        if isinstance(node,dict):
            for key in ("default","minLength","maxLength"): node.pop(key,None)
            if isinstance(node.get("format"),str) and node["format"] not in {"date-time","time","date","duration","email","hostname","ipv4","ipv6","uuid"}:
                node.pop("format")
            if "const" in node: node["enum"]=[node.pop("const")]
            for container in ("properties","$defs","definitions"):
                for value in node.get(container,{}).values(): transport_constraints(value)
            if isinstance(node.get("items"),dict): transport_constraints(node["items"])
            for union in ("anyOf","allOf","oneOf"):
                for value in node.get(union,[]): transport_constraints(value)
    transport_constraints(wire)
    return {"type":"json_schema","name":"pipeline_output","strict":True,"schema":wire},None


class OpenAIClient(LLMClient):
    def __init__(self,settings,*,model=None,diagnostics=None):
        self.settings=settings;self.model_name=model or settings.openai_model
        self.diagnostics=diagnostics or Diagnostics(settings.logs_dir,filename="llm_errors.log",secrets=[settings.openai_api_key.get_secret_value()])
        self.diagnostics.secrets=sorted(set(self.diagnostics.secrets)|{settings.openai_api_key.get_secret_value()}-{ "" },key=len,reverse=True)
        self.progress=lambda message:None;self.request_observer=None
        self.limiter=RateLimiter(settings.cache_dir/"openai_rate_limit.json",limit=settings.openai_rpm_limit,window=60)
        self.client=None

    def _client(self):
        if self.client is None:
            import logging
            from openai import OpenAI
            # SDK import can enable debug from OPENAI_LOG; apply our policy afterwards.
            logging.getLogger("openai").setLevel(logging.WARNING)
            self.client=OpenAI(api_key=self.settings.openai_api_key.get_secret_value(),base_url="https://api.openai.com/v1",
                timeout=self.settings.openai_timeout_sec,max_retries=0)
        return self.client

    def _send(self,prompt,system,*,max_output_tokens,temperature,timeout,text=None):
        kwargs={"model":self.model_name,"input":prompt,"max_output_tokens":max_output_tokens,
                "timeout":timeout or self.settings.openai_timeout_sec,"store":False}
        if system: kwargs["instructions"]=system
        if text is not None: kwargs["text"]={"format":text}
        if temperature is not None: kwargs["temperature"]=temperature
        for attempt in range(self.settings.openai_max_retries+1):
            self.limiter.acquire()
            if self.request_observer is not None: self.request_observer()
            started=time.monotonic()
            try:
                response=self._client().responses.create(**kwargs)
            except Exception as error:
                failure=normalize_error(error,self.diagnostics,"openai")
                self.diagnostics.record_exception(error,f"OpenAI code={failure.code}, attempt={attempt+1}, prompt_chars={len(prompt)}, elapsed_sec={time.monotonic()-started:.3f}")
                if not isinstance(failure,TransientError) or attempt==self.settings.openai_max_retries: raise failure from None
                delay=min(3*2**attempt,48)+random.uniform(0,1)
                message=f"OpenAI quá tải ({failure.code}), thử lại lần {attempt+1}/{self.settings.openai_max_retries} sau {delay:.1f} giây"
                self.progress(message);self.diagnostics.record(message);time.sleep(delay);continue
            self.diagnostics.record(f"OpenAI code=200, attempt={attempt+1}, model={self.model_name}, prompt_chars={len(prompt)}, elapsed_sec={time.monotonic()-started:.3f}")
            if getattr(response,"status",None)=="incomplete":
                reason=getattr(getattr(response,"incomplete_details",None),"reason",None)
                raise OutputError(f"OpenAI phản hồi chưa hoàn tất: {reason or 'unknown'}.",retryable=reason=="max_output_tokens",finish_reason="MAX_TOKENS" if reason=="max_output_tokens" else str(reason))
            if getattr(response,"status",None) in {"failed","cancelled"}: raise OutputError("OpenAI không hoàn tất phản hồi.",retryable=False)
            for output in getattr(response,"output",[]) or []:
                for part in getattr(output,"content",[]) or []:
                    if getattr(part,"type",None)=="refusal": raise OutputError("OpenAI từ chối nội dung yêu cầu.",retryable=False)
            result=getattr(response,"output_text","") or ""
            if not result.strip(): raise OutputError("OpenAI trả output rỗng.",retryable=True)
            return result

    def generate_json(self,prompt,*,system=None,schema=None,max_output_tokens=8192,temperature=None,timeout=None):
        format_info,manual_schema=response_format(schema)
        transport="Return a JSON object only."
        if manual_schema is not None: transport+=" Match this JSON schema; local validation follows: "+json.dumps(manual_schema,ensure_ascii=False)
        raw=self._send(prompt,(system+"\n" if system else "")+transport,max_output_tokens=max_output_tokens,
            temperature=temperature,timeout=timeout,text=format_info)
        return parse_json_object(raw)

    def generate_text(self,prompt,*,system=None,max_output_tokens=8192,temperature=None,timeout=None):
        return self._send(prompt,system,max_output_tokens=max_output_tokens,temperature=temperature,timeout=timeout)

    def close(self):
        if self.client is not None: self.client.close()
