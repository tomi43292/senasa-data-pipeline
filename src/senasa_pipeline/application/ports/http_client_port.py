from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class HttpResponse:
    def __init__(self, status_code: int, text: str, url: str, headers: Mapping[str, str]):
        self.status_code = status_code
        self.text = text
        self.url = url
        self.headers = dict(headers)


class HttpClientPort(Protocol):
    """Minimal HTTP client abstraction (sync or async wrappers behind)."""

    def get(
        self, url: str, *, headers: Mapping[str, str] | None = None, allow_redirects: bool = True
    ) -> HttpResponse: ...
    def post(
        self,
        url: str,
        *,
        data: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        allow_redirects: bool = True,
    ) -> HttpResponse: ...
    def set_cookies(self, cookies: Mapping[str, str]) -> None: ...
    def dump_cookies(self) -> dict[str, str]: ...
