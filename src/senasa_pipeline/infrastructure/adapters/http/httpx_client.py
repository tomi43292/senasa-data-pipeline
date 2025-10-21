from __future__ import annotations
from typing import Mapping, Any
import httpx
from senasa_pipeline.application.ports.http_client_port import HttpClientPort, HttpResponse

class HttpxClient(HttpClientPort):
    """Thin httpx wrapper matching the HttpClientPort.

    Note: synchronous interface por simplicidad inicial. Puede migrarse a async si se requiere.
    """

    def __init__(self, timeout: float = 45.0) -> None:
        self._client = httpx.Client(timeout=timeout, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
            "User-Agent": "senasa-data-pipeline/0.1 httpx",
        }, follow_redirects=True)

    def get(self, url: str, *, headers: Mapping[str, str] | None = None, allow_redirects: bool = True) -> HttpResponse:
        resp = self._client.get(url, headers=headers, follow_redirects=allow_redirects)
        return HttpResponse(resp.status_code, resp.text, str(resp.url), resp.headers)

    def post(self, url: str, *, data: Mapping[str, Any] | None = None, headers: Mapping[str, str] | None = None, allow_redirects: bool = True) -> HttpResponse:
        resp = self._client.post(url, data=data, headers=headers, follow_redirects=allow_redirects)
        return HttpResponse(resp.status_code, resp.text, str(resp.url), resp.headers)

    def set_cookies(self, cookies: Mapping[str, str]) -> None:
        for k, v in cookies.items():
            self._client.cookies.set(k, v)

    def dump_cookies(self) -> dict[str, str]:
        return dict(self._client.cookies)
