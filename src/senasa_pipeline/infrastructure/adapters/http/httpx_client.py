from __future__ import annotations
from typing import Mapping, Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type
from senasa_pipeline.application.ports.http_client_port import HttpClientPort, HttpResponse

class HttpTemporaryError(Exception):
    pass

class HttpxClient(HttpClientPort):
    def __init__(self, timeout: float = 45.0) -> None:
        self._client = httpx.Client(timeout=timeout, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
            "User-Agent": "senasa-data-pipeline/0.1 httpx",
        }, follow_redirects=True)

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=8), retry=retry_if_exception_type(HttpTemporaryError))
    def get(self, url: str, *, headers: Mapping[str, str] | None = None, allow_redirects: bool = True) -> HttpResponse:
        try:
            resp = self._client.get(url, headers=headers, follow_redirects=allow_redirects)
        except httpx.HTTPError as e:
            raise HttpTemporaryError(str(e))
        if resp.status_code >= 500:
            raise HttpTemporaryError(f"GET {url} -> {resp.status_code}")
        return HttpResponse(resp.status_code, resp.text, str(resp.url), resp.headers)

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=8), retry=retry_if_exception_type(HttpTemporaryError))
    def post(self, url: str, *, data: Mapping[str, Any] | None = None, headers: Mapping[str, str] | None = None, allow_redirects: bool = True) -> HttpResponse:
        try:
            resp = self._client.post(url, data=data, headers=headers, follow_redirects=allow_redirects)
        except httpx.HTTPError as e:
            raise HttpTemporaryError(str(e))
        if resp.status_code >= 500:
            raise HttpTemporaryError(f"POST {url} -> {resp.status_code}")
        return HttpResponse(resp.status_code, resp.text, str(resp.url), resp.headers)

    def set_cookies(self, cookies: Mapping[str, str]) -> None:
        for k, v in cookies.items():
            self._client.cookies.set(k, v)

    def dump_cookies(self) -> dict[str, str]:
        return dict(self._client.cookies)
