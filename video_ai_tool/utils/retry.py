# file: utils/retry.py
"""Retry lỗi tạm thời; không thử lại lỗi xác thực hoặc input sai."""
from collections.abc import Callable
from typing import Any
import requests
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

def is_transient_error(error: BaseException) -> bool:
    if isinstance(error, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(error, requests.HTTPError) and error.response is not None:
        return error.response.status_code in {408, 429, 500, 502, 503, 504}
    return False


def network_retry(attempts: int = 3) -> Callable[..., Any]:
    if attempts < 1:
        raise ValueError("Số lần thử phải lớn hơn 0.")
    return retry(retry=retry_if_exception(is_transient_error), stop=stop_after_attempt(attempts),
                 wait=wait_exponential_jitter(initial=1, max=30), reraise=True)


def request_json(method: str, url: str, *, timeout: float = 30, attempts: int = 3, **kwargs: Any) -> Any:
    """Wrapper HTTP có timeout và retry 429/5xx; không log URL chứa key."""
    if timeout <= 0:
        raise ValueError("Timeout phải lớn hơn 0.")

    @network_retry(attempts)
    def send() -> Any:
        with requests.request(method, url, timeout=timeout, **kwargs) as response:
            response.raise_for_status()
            return response.json()

    return send()
