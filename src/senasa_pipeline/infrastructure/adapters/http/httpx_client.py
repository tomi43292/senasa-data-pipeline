from __future__ import annotations
from typing import Mapping, Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type
from senasa_pipeline.application.ports.http_client_port import HttpClientPort, HttpResponse

class HttpTemporaryError(Exception):
    pass

class HttpxClient(HttpClientPort):
    def __init__(self, timeout: float = 45.0) -> None:
        """HTTP client adapter backed by a persistent httpx.Client.

        - Persists cookies across requests automatically (cookie jar)
        - Exposes dump_cookies/set_cookies to comply with the port
        - Adds lightweight diagnostics for cookies and Set-Cookie headers
        
        Args:
            timeout (float, optional): Timeout for requests. Defaults to 45.0.
        """
        self._client = httpx.Client(timeout=timeout, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
            "User-Agent": "senasa-data-pipeline/0.1 httpx",
        }, follow_redirects=True)

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=8), retry=retry_if_exception_type(HttpTemporaryError))
    def get(self, url: str, *, headers: Mapping[str, str] | None = None, allow_redirects: bool = True) -> HttpResponse:
        """Gets the given URL.
        
        Args:
            url (str): URL to get.
            headers (Mapping[str, str] | None, optional): Headers to include. Defaults to None.
            allow_redirects (bool, optional): Whether to allow redirects. Defaults to True.
        
        Returns:
            HttpResponse: Response from the server.
        """
        try:
            resp = self._client.get(
                url,
                headers=headers,
                cookies=self._client.cookies,
                follow_redirects=allow_redirects,
            )
        except httpx.HTTPError as e:
            raise HttpTemporaryError(str(e))
        if resp.status_code >= 500:
            raise HttpTemporaryError(f"GET {url} -> {resp.status_code}")
        return HttpResponse(resp.status_code, resp.text, str(resp.url), resp.headers, raw=resp)

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=8), retry=retry_if_exception_type(HttpTemporaryError))
    def post(self, url: str, *, data: Mapping[str, Any] | None = None, headers: Mapping[str, str] | None = None, allow_redirects: bool = True) -> HttpResponse:
        """Posts data to the given URL.
        
        Args:
            url (str): URL to post to.
            data (Mapping[str, Any] | None, optional): Data to post. Defaults to None.
            headers (Mapping[str, str] | None, optional): Headers to include. Defaults to None.
            allow_redirects (bool, optional): Whether to allow redirects. Defaults to True.
        
        Returns:
            HttpResponse: Response from the server.
        """
        try:
            resp = self._client.post(
                url,
                data=data,
                headers=headers,
                cookies=self._client.cookies,
                follow_redirects=allow_redirects,
            )
        except httpx.HTTPError as e:
            raise HttpTemporaryError(str(e))
        if resp.status_code >= 500:
            raise HttpTemporaryError(f"POST {url} -> {resp.status_code}")
        return HttpResponse(resp.status_code, resp.text, str(resp.url), resp.headers, raw=resp)

    def set_cookies(self, cookies: Mapping[str, str]) -> None:
        """Sets cookies in the client.
        
        Args:
            cookies (Mapping[str, str]): Cookies to set.
        """
        self._client.cookies.update(dict(cookies))

    def dump_cookies(self) -> dict[str, str]:
        """Dumps cookies from the client.
        
        Returns:
            dict[str, str]: Cookies from the client.
        """
        return dict(self._client.cookies)
