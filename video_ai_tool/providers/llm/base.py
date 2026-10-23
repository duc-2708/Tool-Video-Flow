"""SDK-independent interfaces and safe, normalized error types."""
from abc import ABC, abstractmethod
from providers.llm_base import ProviderError


class LLMError(ProviderError):
    def __init__(self, message, *, code=None):
        super().__init__(message)
        self.code = code


class TransientError(LLMError): pass
class RateLimitError(TransientError): pass
class TimeoutError(TransientError): pass
class AuthError(LLMError): pass
class BadRequestError(LLMError): pass
class ConfigurationError(LLMError): pass


class OutputError(LLMError):
    def __init__(self, message, *, retryable, finish_reason=None):
        super().__init__(message)
        self.retryable, self.finish_reason = retryable, finish_reason


# Stable legacy exception identities for agent/Style callers and checkpoints.
class GeminiRequestError(LLMError):
    def __init__(self, code, message):
        super().__init__(message, code=code)


class GeminiTransientError(GeminiRequestError, TransientError): pass
GeminiOutputError = OutputError


def normalize_error(error, diagnostics, provider):
    if isinstance(error, LLMError) and not isinstance(error,GeminiTransientError):
        return error
    import builtins
    from providers.gemini_resilience import error_code
    code = getattr(error, "status_code", None) or error_code(error)
    message = diagnostics.redact(f"{provider}: {error}")
    if code == 429:
        return RateLimitError(message, code=code)
    if code in {408, 504, "TIMEOUT", "DEADLINE_EXCEEDED"} or isinstance(error, builtins.TimeoutError) or "timeout" in type(error).__name__.lower():
        return TimeoutError(message, code=code or "TIMEOUT")
    if code in {401, 403}:
        return AuthError(message, code=code)
    if isinstance(code, int) and code >= 500 or code == "UNAVAILABLE" or type(error).__name__ == "APIConnectionError":
        return TransientError(message, code=code)
    return BadRequestError(message, code=code)


class LLMClient(ABC):
    @abstractmethod
    def generate_json(self, prompt, *, system=None, schema=None, max_output_tokens=8192,
                      temperature=None, timeout=None) -> dict: ...

    @abstractmethod
    def generate_text(self, prompt, *, system=None, max_output_tokens=8192,
                      temperature=None, timeout=None) -> str: ...

    def close(self): pass
