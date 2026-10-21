# file: utils/text.py
"""Làm sạch văn bản và tên thư mục an toàn trên Windows."""
import re
import unicodedata


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def slugify(text: str, max_length: int = 80) -> str:
    if max_length < 1:
        raise ValueError("max_length phải lớn hơn 0.")
    normalized = unicodedata.normalize("NFKD", text.lower().replace("đ", "d"))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:max_length].rstrip("-") or "video"
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
    return f"video-{slug}" if slug in reserved else slug


def split_sentences(text: str) -> list[str]:
    return [part for part in re.split(r"(?<=[.!?…])\s+", clean_text(text)) if part]
