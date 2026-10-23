"""Text adapter preserving Gemini retries, compaction, fallback and observers."""
from pydantic import BaseModel
from providers.llm.base import LLMClient, OutputError, normalize_error
from utils.json_response import parse_json_object


class TextEnvelope(BaseModel):
    text: str


class GeminiClient(LLMClient):
    def __init__(self, settings, *, model=None, diagnostics=None):
        self.settings=settings.model_copy(update={"gemini_model":model or settings.gemini_model})
        self.model_name=self.settings.gemini_model
        self.diagnostics=diagnostics
        self.progress=lambda message:None
        self.request_observer=None
        self.backend=None
        self._timeout=None

    def _backend(self,timeout):
        desired=timeout if timeout is not None else self.settings.gemini_timeout_sec
        if self.backend is None or desired!=self._timeout:
            if self.backend is not None: self.backend.close()
            from providers.llm_gemini import GeminiProvider
            self.backend=GeminiProvider(self.settings.model_copy(update={"gemini_timeout_sec":desired}))
            self._timeout=desired
        if self.diagnostics is not None: self.backend.diagnostics=self.diagnostics
        self.backend.progress=self.progress
        self.backend.request_observer=self.request_observer
        return self.backend

    def generate_json(self,prompt,*,system=None,schema=None,max_output_tokens=8192,temperature=None,timeout=None):
        backend=self._backend(timeout)
        backend.output_token_budget=max_output_tokens
        backend.temperature=.2 if temperature is None else temperature
        backend.system_instruction=system
        try:
            if isinstance(schema,type) and issubclass(schema,BaseModel):
                raw=backend.generate_json(prompt,schema)
            else:
                from google.genai import types
                config=types.GenerateContentConfig(response_mime_type="application/json",response_json_schema=schema,
                    max_output_tokens=max_output_tokens,temperature=backend.temperature,system_instruction=system)
                response=backend._send_with_retry(prompt,config,None)
                reasons={str(getattr(c.finish_reason,"value",c.finish_reason)) for c in (response.candidates or [])}
                feedback=getattr(response,"prompt_feedback",None);block=getattr(feedback,"block_reason",None)
                if getattr(block,"value",block) not in (None,"","BLOCK_REASON_UNSPECIFIED") or reasons & {"SAFETY","RECITATION","BLOCKLIST","PROHIBITED_CONTENT","SPII"}:
                    raise OutputError("Gemini chặn nội dung.",retryable=False)
                if "MAX_TOKENS" in reasons:
                    raise OutputError("Gemini cắt output vì MAX_TOKENS.",retryable=True,finish_reason="MAX_TOKENS")
                raw=response.text or ""
            return parse_json_object(raw)
        except (OutputError,ValueError): raise
        except Exception as error:
            raise normalize_error(error,backend.diagnostics,"gemini") from None

    def generate_text(self,prompt,*,system=None,max_output_tokens=8192,temperature=None,timeout=None):
        return self.generate_json(prompt,system=system,schema=TextEnvelope,max_output_tokens=max_output_tokens,
                                  temperature=temperature,timeout=timeout)["text"]

    def close(self):
        if self.backend is not None: self.backend.close()
