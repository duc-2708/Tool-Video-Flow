# file: providers/llm_gemini.py
"""Gemini structured output, timeout và retry lỗi mạng tạm thời."""
import httpx
import json
import math
from google import genai
from google.genai import errors, types
from pydantic import BaseModel
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential_jitter
from config.settings import Settings
from providers.llm_base import LLMProvider, ProviderError
from utils.diagnostics import Diagnostics
from providers.research_payload import ResearchFactsResponse,compact_facts_json,reduced_request_prompt
from providers.style_schema import response_schema


class GeminiRequestError(ProviderError):
    def __init__(self,code,message):
        super().__init__(message)
        self.code = code


class GeminiOutputError(ProviderError):
    """Phân biệt output rỗng/cắt token với API hoặc lỗi parse JSON."""
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


def transient_gemini(error: BaseException) -> bool:
    return isinstance(error, (httpx.TimeoutException, httpx.NetworkError)) or (
        isinstance(error, errors.APIError) and error.code in {408, 429, 500, 502, 503, 504})


class GeminiProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self.diagnostics = Diagnostics(settings.logs_dir, secrets=[settings.gemini_api_key.get_secret_value()])
        self._model = settings.require_gemini_model()
        self.attempts = settings.retry_attempts
        self.output_token_budget = 8192
        self.client = genai.Client(api_key=settings.require_key("gemini"), http_options=types.HttpOptions(
            timeout=int(settings.request_timeout_sec * 1000),
            retry_options=types.HttpRetryOptions(attempts=1)))

    @property
    def model_name(self) -> str:
        return self._model

    def generate_json(self, prompt: str, schema: type[BaseModel]) -> str:
        from schemas.research_brief import ResearchBrief
        wire_schema = ResearchFactsResponse if schema is ResearchBrief else schema
        fallback = getattr(self,"_plain_json_mode",False)
        if fallback:
            prompt = reduced_request_prompt(prompt,wire_schema)
        while True:
            try:
                result = self._generate_json(prompt,wire_schema,minimal=fallback)
                return compact_facts_json(result) if schema is ResearchBrief else result
            except GeminiRequestError as error:
                if error.code != 400 or fallback:
                    raise
                fallback = True
                self._plain_json_mode = True
                self.diagnostics.record("Gemini HTTP 400: thử đúng một lần với đầu vào/schema rút gọn; bỏ response_json_schema, response_mime_type, max_output_tokens, temperature. Lỗi gốc: "+str(error))
                prompt = reduced_request_prompt(prompt,wire_schema)

    def generate_media_json(self, prompt: str, media, schema: type[BaseModel]) -> str:
        """Reuse output/safety/timeout handling for a temporary Files API part."""
        try:
            return self._generate_json(prompt, schema, media=media)
        except GeminiRequestError as error:
            if error.code != 400:
                raise
            self.diagnostics.record("Style HTTP 400: thử một lần JSON không có response schema; giữ nguyên prompt phân tích.")
            fallback = prompt + "\nChỉ trả JSON theo schema:\n" + json.dumps(schema.model_json_schema(), ensure_ascii=False)
            return self._generate_json(fallback, schema, minimal=True, media=media)

    def _generate_json(self, prompt: str, schema: type[BaseModel], *, minimal=False, media=None) -> str:
        try:
            self.diagnostics.record(f"Gemini request: model={self._model}, prompt_chars={len(prompt)}, estimated_input_tokens={math.ceil(len(prompt)/3)}, schema_chars={len(json.dumps(response_schema(schema)))}, mode={'plain_json_fallback' if minimal else 'structured_json'}, max_output_tokens={'model_default' if minimal else self.output_token_budget}, thinking_config=none")
            for attempt in Retrying(retry=retry_if_exception(transient_gemini),
                                    stop=stop_after_attempt(self.attempts),
                                    before_sleep=lambda state: self.diagnostics.record_exception(
                                        state.outcome.exception(), f"Gemini transient failure, attempt={state.attempt_number}"),
                                    wait=wait_exponential_jitter(initial=1, max=30), reraise=True):
                with attempt:
                    response = self.client.models.generate_content(model=self._model, contents=[media, prompt] if media is not None else prompt,
                        config=types.GenerateContentConfig() if minimal else types.GenerateContentConfig(response_mime_type="application/json",
                            # JSON Schema phải đi qua response_json_schema; response_schema
                            # là Schema kiểu OpenAPI, SDK đổi additionalProperties thành
                            # additional_properties không hợp lệ ở endpoint đang dùng.
                            response_json_schema=response_schema(schema),
                            max_output_tokens=self.output_token_budget, temperature=0.2))
                    candidates = response.candidates if isinstance(response.candidates, list) else []
                    reasons = [str(getattr(candidate.finish_reason, "value", candidate.finish_reason)) for candidate in candidates]
                    feedback = getattr(response, "prompt_feedback", None)
                    block = getattr(feedback, "block_reason", None)
                    block_reason = getattr(block, "value", block)
                    if isinstance(block_reason, str) and block_reason not in {"", "BLOCK_REASON_UNSPECIFIED"}:
                        raise GeminiOutputError(f"Gemini chặn prompt: {block_reason}.", retryable=False)
                    if any(reason in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "IMAGE_SAFETY"} for reason in reasons):
                        raise GeminiOutputError(f"Gemini chặn output: {','.join(reasons)}.", retryable=False)
                    if "MAX_TOKENS" in reasons:
                        self.output_token_budget = min(self.output_token_budget * 2, 32768)
                        raise GeminiOutputError("Gemini cắt output vì MAX_TOKENS; tăng ngân sách token cho lần thử kế tiếp.", retryable=True)
                    text = response.text or ""
                    if not text.strip():
                        raise GeminiOutputError(f"Gemini trả output rỗng; finish_reason={','.join(reasons) or 'không có candidate'}.", retryable=True)
                    self.diagnostics.record(f"Gemini response: finish_reason={','.join(reasons) or 'unknown'}, output_chars={len(text)}, max_output_tokens={self.output_token_budget}")
                    return text
        except GeminiOutputError as error:
            self.diagnostics.record_exception(error, "Gemini output status")
            raise
        except errors.APIError as error:
            self.diagnostics.record_exception(error, "Gemini generate_content: API error")
            if error.code in {401, 403}:
                raise ProviderError("Gemini từ chối xác thực/quyền truy cập. Kiểm tra key và model trong .env.") from None
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
