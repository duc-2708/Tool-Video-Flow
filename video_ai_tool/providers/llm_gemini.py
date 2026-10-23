# file: providers/llm_gemini.py
"""Gemini structured output, timeout và retry lỗi mạng tạm thời."""
import httpx
import json
import math
import random
import time
from google import genai
from google.genai import errors, types
from pydantic import BaseModel
from config.settings import Settings
from providers.llm_base import LLMProvider, ProviderError
from utils.diagnostics import Diagnostics
from providers.research_payload import ResearchFactsResponse,compact_facts_json
from providers.style_schema import response_schema
from providers.gemini_resilience import transient_gemini,error_code,compact_prompt
from providers.llm.base import GeminiRequestError, GeminiOutputError, GeminiTransientError, AuthError


class GeminiProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self.diagnostics = Diagnostics(settings.logs_dir, secrets=[settings.gemini_api_key.get_secret_value()])
        self._model = settings.require_gemini_model()
        self.attempts = 6  # Original request plus at most five retries.
        self.fallback_model=settings.gemini_fallback_model.strip()
        self.progress=lambda message:None
        self.output_token_budget = 8192
        self.client = genai.Client(api_key=settings.require_key("gemini"), http_options=types.HttpOptions(
            timeout=int(settings.gemini_timeout_sec * 1000),
            retry_options=types.HttpRetryOptions(attempts=1)))

    @property
    def model_name(self) -> str:
        return self._model

    def generate_json(self, prompt: str, schema: type[BaseModel]) -> str:
        from schemas.research_brief import ResearchBrief
        wire_schema = ResearchFactsResponse if schema is ResearchBrief else schema
        result = self._generate_json(prompt,wire_schema)
        return compact_facts_json(result) if schema is ResearchBrief else result

    def generate_media_json(self, prompt: str, media, schema: type[BaseModel]) -> str:
        """Reuse output/safety/timeout handling for a temporary Files API part."""
        return self._generate_json(prompt, schema, media=media)

    def _send_with_retry(self,prompt,config,media):
        model=self._model;deadline_failures=0;reduced=False;used_fallback=False
        for index in range(self.attempts):
            observer=getattr(self,"request_observer",None)
            if observer is not None: observer()  # Rate/quota observers run before every paid attempt.
            started=time.monotonic()
            if media is not None:
                wire=config.response_json_schema or config.response_schema
                metadata=getattr(media,"video_metadata",None)
                self.diagnostics.record("Gemini media request: "+json.dumps({
                    "model":model,"max_output_tokens":config.max_output_tokens,"media_resolution":config.media_resolution,
                    "response_mime_type":config.response_mime_type,"schema_chars":len(json.dumps(wire,ensure_ascii=False,default=str)) if wire else 0,
                    "has_response_schema":config.response_schema is not None,"has_response_json_schema":config.response_json_schema is not None,
                    "thinking_config":config.thinking_config.model_dump(mode="json") if config.thinking_config else None,
                    "prompt_chars":len(prompt),"video_metadata":metadata.model_dump(mode="json",exclude_none=True) if metadata else None,
                    "video":getattr(self,"video_request_context",{}),"attempt":index+1},ensure_ascii=False,default=str))
            try:
                response=self.client.models.generate_content(model=model,contents=[media,prompt] if media is not None else prompt,config=config)
            except Exception as error:
                code=error_code(error)
                self.diagnostics.record_exception(error,f"Gemini attempt={index+1}, code={code}, model={model}, prompt_chars={len(prompt)}, estimated_input_tokens={math.ceil(len(prompt)/3)}, elapsed_sec={time.monotonic()-started:.3f}")
                if media is not None and code==400:
                    payload={"code":code,"status":getattr(error,"status",None),"message":getattr(error,"message",None),
                        "details":getattr(error,"details",None),"original":str(error)}
                    body=getattr(getattr(error,"response",None),"text",None)
                    if isinstance(body,str): payload["response_body"]=body
                    self.diagnostics.record("Gemini media 400 response (nguyên văn, đã che key): "+json.dumps(payload,ensure_ascii=False,default=str))
                if not transient_gemini(error): raise
                if index==self.attempts-1:
                    raise GeminiTransientError(code,f"Gemini tạm thời không sẵn sàng ({code}) sau {self.attempts} lần gọi. Đã giữ tiến độ; chạy Tiếp tục để thử lại lượt đang dở. Chi tiết: {self.diagnostics.path}.") from error
                if code in {504,"TIMEOUT"}:
                    deadline_failures+=1
                    if deadline_failures>=2 and not reduced:
                        original=len(prompt);prompt=compact_prompt(prompt);reduced=True
                        self.diagnostics.record(f"Gemini compact after {code}: prompt_chars={original} -> {len(prompt)}; giữ nguyên ID và fact đang tham chiếu.")
                        self.progress("Gemini hết thời gian xử lý lặp lại; rút gọn hồ sơ phong cách và dữ liệu không dùng.")
                    elif deadline_failures>=3 and reduced and self.fallback_model and self.fallback_model!=model and not used_fallback:
                        model=self.fallback_model;used_fallback=True
                        self.diagnostics.record(f"Gemini fallback: model={model}, prompt_chars={len(prompt)}")
                        self.progress(f"Gemini vẫn quá tải; chuyển sang model dự phòng {model}.")
                delay=3*2**index+random.uniform(0,1)
                message=f"Gemini quá tải ({code}), thử lại lần {index+1}/5 sau {delay:.1f} giây"
                self.diagnostics.record(message)
                self.progress(message)
                time.sleep(delay)
                continue
            self.diagnostics.record(f"Gemini attempt={index+1}, code=200, model={model}, prompt_chars={len(prompt)}, estimated_input_tokens={math.ceil(len(prompt)/3)}, elapsed_sec={time.monotonic()-started:.3f}")
            return response

    def _generate_json(self, prompt: str, schema: type[BaseModel], *, minimal=False, media=None) -> str:
        try:
            self.diagnostics.record(f"Gemini request: model={self._model}, prompt_chars={len(prompt)}, estimated_input_tokens={math.ceil(len(prompt)/3)}, schema_chars={len(json.dumps(response_schema(schema)))}, mode={'plain_json_fallback' if minimal else 'structured_json'}, max_output_tokens={'model_default' if minimal else self.output_token_budget}, thinking_config=none")
            config=types.GenerateContentConfig() if minimal else types.GenerateContentConfig(response_mime_type="application/json",
                    # JSON Schema phải đi qua response_json_schema; response_schema
                    # là Schema kiểu OpenAPI, SDK đổi additionalProperties thành
                    # additional_properties không hợp lệ ở endpoint đang dùng.
                    response_json_schema=response_schema(schema),
                    max_output_tokens=self.output_token_budget, temperature=getattr(self,"temperature",0.2),
                    system_instruction=getattr(self,"system_instruction",None))
            if media is not None:
                options=getattr(self,"media_request_options",{})
                if options:
                    config.response_json_schema=options["wire_schema"] if options["use_schema"] else None
                    config.response_schema=None
                config.response_mime_type="application/json"
                config.max_output_tokens=options.get("max_output_tokens",self.output_token_budget)
                resolution=options.get("media_resolution",getattr(self,"media_resolution",None))
                if resolution is not None:
                    config.media_resolution=types.MediaResolution("MEDIA_RESOLUTION_"+resolution.upper())
            response = self._send_with_retry(prompt,config,media)
            candidates = response.candidates if isinstance(response.candidates, list) else []
            reasons = [str(getattr(candidate.finish_reason, "value", candidate.finish_reason)) for candidate in candidates]
            feedback = getattr(response, "prompt_feedback", None)
            block = getattr(feedback, "block_reason", None)
            block_reason = getattr(block, "value", block)
            text = response.text or ""
            response_observer=getattr(self,"response_observer",None)
            if response_observer is not None:
                blocked=(isinstance(block_reason,str) and block_reason not in {"","BLOCK_REASON_UNSPECIFIED"}) or any(reason in {"SAFETY","RECITATION","BLOCKLIST","PROHIBITED_CONTENT","SPII","IMAGE_SAFETY"} for reason in reasons)
                try:
                    response_observer(text,{"finish_reasons":reasons,"blocked":blocked,"truncated":"MAX_TOKENS" in reasons})
                except Exception as error:
                    raise GeminiOutputError("Không lưu được phản hồi thô; dừng để tránh mất kết quả đã tốn token.",retryable=False) from error
            if isinstance(block_reason, str) and block_reason not in {"", "BLOCK_REASON_UNSPECIFIED"}:
                raise GeminiOutputError(f"Gemini chặn prompt: {block_reason}.", retryable=False)
            if any(reason in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "IMAGE_SAFETY"} for reason in reasons):
                raise GeminiOutputError(f"Gemini chặn output: {','.join(reasons)}.", retryable=False)
            if "MAX_TOKENS" in reasons:
                if media is None:
                    self.output_token_budget = min(self.output_token_budget * 2, 32768)
                raise GeminiOutputError("Gemini cắt output vì MAX_TOKENS.", retryable=True,finish_reason="MAX_TOKENS")
            if not text.strip():
                raise GeminiOutputError(f"Gemini trả output rỗng; finish_reason={','.join(reasons) or 'không có candidate'}.", retryable=True)
            self.diagnostics.record(f"Gemini response: finish_reason={','.join(reasons) or 'unknown'}, output_chars={len(text)}, max_output_tokens={self.output_token_budget}")
            return text
        except GeminiTransientError:
            raise
        except GeminiOutputError as error:
            self.diagnostics.record_exception(error, "Gemini output status")
            raise
        except errors.APIError as error:
            self.diagnostics.record_exception(error, "Gemini generate_content: API error")
            if error.code in {401, 403}:
                raise AuthError("Gemini từ chối xác thực/quyền truy cập. Kiểm tra GEMINI_API_KEY và model trong .env.",code=error.code) from None
            if error.code == 429:
                raise ProviderError("Gemini hết quota hoặc bị giới hạn tốc độ. Thử lại sau.") from None
            if error.code == 400:
                detail = self.diagnostics.redact(str(error))
                self.diagnostics.record("Gemini HTTP 400 nguyên văn (đã che credentials): "+detail)
                raise GeminiRequestError(400,detail) from None
            raise ProviderError(f"Gemini HTTP {error.code}: yêu cầu không xử lý được; xem {self.diagnostics.path}.") from None
        except (httpx.HTTPError, OSError) as error:
            self.diagnostics.record_exception(error, "Gemini generate_content: network error")
            raise ProviderError("Không kết nối được Gemini sau các lần thử. Kiểm tra mạng/proxy.") from None
        except Exception as error:
            self.diagnostics.record_exception(error, "Gemini generate_content: SDK/schema error")
            raise ProviderError(f"Gemini SDK/schema gặp lỗi; xem {self.diagnostics.path}.") from None
        raise ProviderError("Gemini chưa trả kết quả.")

    def close(self) -> None:
        self.client.close()
