# file: providers/llm_base.py
"""Hợp đồng LLM độc lập SDK, không thực thi output AI."""
from abc import ABC, abstractmethod
from pydantic import BaseModel


class ProviderError(RuntimeError):
    """Thông báo an toàn, không chứa lỗi HTTP thô."""


class LLMProvider(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Định danh model để phân biệt cache, không chứa credentials."""
        raise NotImplementedError

    @abstractmethod
    def generate_json(self, prompt: str, schema: type[BaseModel]) -> str:
        """Trả JSON text. Caller validate và retry nội dung."""
        raise NotImplementedError
