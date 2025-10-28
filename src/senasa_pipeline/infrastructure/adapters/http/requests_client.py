from __future__ import annotations

from typing import Mapping, Any
import requests

from senasa_pipeline.application.ports.http_client_port import HttpClientPort, HttpResponse


class RequestsHttpClient(HttpClientPort):
    """HTTP client adapter backed by a persistent requests.Session.

    - Persists cookies across requests automatically (cookie jar)
    - Exposes dump_cookies/set_cookies to comply with the port
    - Adds lightweight diagnostics for cookies and Set-Cookie headers
    """

    def __init__(self, default_headers: Mapping[str, str] | None = None) -> None:
        self.session = requests.Session()
        if default_headers:
            self.session.headers.update(dict(default_headers))

    def _log(self, msg: str) -> None:
        print(f"[RequestsHttpClient] {msg}")

    def _cookie_preview(self) -> str:
        jar = self.session.cookies.get_dict()
        if not jar:
            return "-"
        pairs = [f"{k}={v}" for k, v in jar.items()]
        return "; ".join(pairs)[:240]

    def get(self, url: str, *, headers: Mapping[str, str] | None = None, allow_redirects: bool = True) -> HttpResponse:
        self._log(f"GET {url} | cookies: {list(self.session.cookies.get_dict().keys())} | Cookie: {self._cookie_preview()}")
        resp = self.session.get(url, headers=headers, allow_redirects=allow_redirects)
        set_cookie = resp.headers.get("Set-Cookie", "")
        if set_cookie:
            self._log(f"GET {url} | Set-Cookie: {set_cookie[:240]}...")
        return HttpResponse(resp.status_code, resp.text, str(resp.url), resp.headers)

    def post(
        self,
        url: str,
        *,
        data: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        allow_redirects: bool = True,
    ) -> HttpResponse:
        self._log(f"POST {url} | cookies: {list(self.session.cookies.get_dict().keys())} | Cookie: {self._cookie_preview()}")
        resp = self.session.post(url, data=data, headers=headers, allow_redirects=allow_redirects)
        set_cookie = resp.headers.get("Set-Cookie", "")
        if set_cookie:
            self._log(f"POST {url} | Set-Cookie: {set_cookie[:240]}...")
        return HttpResponse(resp.status_code, resp.text, str(resp.url), resp.headers)

    def set_cookies(self, cookies: Mapping[str, str]) -> None:
        self.session.cookies.update(dict(cookies))
        self._log(f"set_cookies -> now: {list(self.session.cookies.get_dict().keys())}")

    def dump_cookies(self) -> dict[str, str]:
        jar = self.session.cookies.get_dict()
        self._log(f"dump_cookies -> {list(jar.keys())}")
        return jar
