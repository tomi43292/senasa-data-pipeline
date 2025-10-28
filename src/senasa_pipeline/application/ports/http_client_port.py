from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol
import json


class HttpResponse:
    def __init__(
        self,
        status_code: int,
        text: str,
        url: str,
        headers: Mapping[str, str],
        *,
        raw: Any | None = None,
    ) -> None:
        self.status_code = status_code
        self.text = text
        self.url = url
        self.headers = dict(headers)
        self._raw = raw

    @property
    def request(self) -> Any:
        if self._raw is None or not hasattr(self._raw, "request"):
            raise AttributeError("request not available")
        return self._raw.request

    def json(self) -> Any:
        if self._raw is not None and hasattr(self._raw, "json"):
            return self._raw.json()
        return json.loads(self.text)


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
