from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from senasa_pipeline.application.ports.http_client_port import HttpClientPort
from senasa_pipeline.application.ports.senasa_login_port import SenasaLoginPort

SENASA_BASE = "https://trazabilidadapicola.senasa.gob.ar"


class SenasaLoginConsumer(SenasaLoginPort):
    """Completa login SENASA a partir de token/sign y valida sesión."""

    def __init__(self, http: HttpClientPort) -> None:
        self.http = http
        self.cookies: dict[str, str] = {}

    def login_with_token_sign(self, token: str, sign: str) -> None:
        # 1) POST /afip con token/sign
        headers = {
            "Origin": "https://portalcf.cloud.afip.gob.ar",
            "Referer": "https://portalcf.cloud.afip.gob.ar/portal/app/",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        self.http.post(
            f"{SENASA_BASE}/afip",
            data={"token": token, "sign": sign},
            headers=headers,
            allow_redirects=True,
        )
        # 2) GET Login.aspx?from=afip y auto-submit si hay form
        login_url = f"{SENASA_BASE}/Login.aspx?from=afip"
        resp = self.http.get(login_url)
        soup = BeautifulSoup(resp.text, "html.parser")
        form = soup.find("form")
        if form:
            action = form.get("action") or login_url
            post_url = urljoin(login_url, action)
            payload = {
                inp.get("name"): inp.get("value", "")
                for inp in form.find_all("input")
                if inp.get("name")
            }
            self.http.post(
                post_url,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded", "Referer": login_url},
            )
        # 3) Guardar cookies actuales
        self.cookies = self.http.dump_cookies()

    def validate_session(self) -> bool:
        # No seguir redirects para detectar Login.aspx
        probe = self.http.get(f"{SENASA_BASE}/Sur/Extracciones/List", allow_redirects=False)
        if probe.status_code in (301, 302, 303, 307, 308):
            loc = probe.headers.get("Location", "")
            if "/Login.aspx" in loc:
                return False
        if probe.status_code == 200 and (
            'name="__VIEWSTATE"' in probe.text or "__VIEWSTATE" in probe.text
        ):
            return True
        return False
