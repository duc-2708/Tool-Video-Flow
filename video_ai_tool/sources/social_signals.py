# file: sources/social_signals.py
"""Interface dự phòng; MVP không scrape TikTok/Facebook/Instagram."""
from typing import Protocol
from schemas.source import SourceDocument


class SocialSignalsProvider(Protocol):
    def search(self, topic: str) -> list[SourceDocument]:
        raise NotImplementedError


class DisabledSocialSignals:
    def search(self, topic: str) -> list[SourceDocument]:
        return []


if __name__ == "__main__":
    from utils.console import configure_console
    configure_console()
    print("MVP không scrape TikTok/Facebook/Instagram. Chưa cấu hình provider bên thứ ba.")
