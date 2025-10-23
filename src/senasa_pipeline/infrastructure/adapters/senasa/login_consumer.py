from __future__ import annotations
from urllib.parse import urljoin
from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from senasa_pipeline.application.ports.http_client_port import HttpClientPort
from senasa_pipeline.application.ports.senasa_login_port import SenasaLoginPort

SENASA_BASE = "https://trazabilidadapicola.senasa.gob.ar"

class SenasaLoginConsumer(SenasaLoginPort):
    """Completa login SENASA a partir de token/sign y realiza selección de usuario en Login.aspx."""

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
        self.http.post(f"{SENASA_BASE}/afip", data={"token": token, "sign": sign}, headers=headers, allow_redirects=True)

        # 2) Aterrizar en Login.aspx?from=afip y procesar posibles forms intermedios
        login_url = f"{SENASA_BASE}/Login.aspx?from=afip"
        resp = self.http.get(login_url, allow_redirects=True)
        html = resp.text or ""
        soup = BeautifulSoup(html, "html.parser")

        # Si hay un form con token/sign (auto-submit), replicar envío para aterrizar en Login.aspx real
        form = soup.find("form")
        if form and form.find("input", {"name": "token"}) and form.find("input", {"name": "sign"}):
            action = form.get("action") or login_url
            post_url = urljoin(login_url, action)
            payload = {inp.get("name"): inp.get("value", "") for inp in form.find_all("input") if inp.get("name")}
            self.http.post(post_url, data=payload, headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": SENASA_BASE,
                "Referer": f"{SENASA_BASE}/afip",
            })
            # refrescar html de Login.aspx
            resp = self.http.get(login_url)
            soup = BeautifulSoup(resp.text or "", "html.parser")

        # 3) Extraer campos ocultos (__VIEWSTATE, etc.)
        hidden: dict[str, str] = {}
        for inp in soup.find_all("input", {"type": "hidden", "name": True}):
            hidden[inp["name"]] = inp.get("value", "")

        # 4) Ubicar botón del usuario AFIP (por id conocido o por texto de la cooperativa)
        btn = soup.find('a', id='ctl00_MasterEditBox_ucLogin_rptUsuariosAfip_ctl05_btnLoginAfip')
        if not btn:
            btn = soup.find('a', string=lambda t: t and 'COOP. APICOLA DEL PARANA' in t)
        # Si no hay botón, asumir que ya quedó autenticado o no requiere selección
        if btn:
            btn_id = btn.get('id', 'ctl00_MasterEditBox_ucLogin_rptUsuariosAfip_ctl05_btnLoginAfip')
            event_target = btn_id.replace('_', '$')

            payload = hidden.copy()
            payload.update({
                "ctl00$ScriptManager1": f"ctl00$updatePanelEdit|{event_target}",
                "__EVENTTARGET": event_target,
                "__EVENTARGUMENT": "",
                "__ASYNCPOST": "true",
            })
            payload.setdefault("__LASTFOCUS", "")
            payload.setdefault("__SCROLLPOSITIONX", "0")
            payload.setdefault("__SCROLLPOSITIONY", "0")
            payload.setdefault("ctl00$hiddenPendingDownload", "")

            ajax_headers = {
                "Accept": "*/*",
                "x-microsoftajax": "Delta=true",
                "x-requested-with": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Referer": login_url,
            }
            self.http.post(login_url, data=payload, headers=ajax_headers)

        # 5) Guardar cookies actuales
        self.cookies = self.http.dump_cookies()

    def validate_session(self) -> bool:
        # No seguir redirects para detectar Login.aspx
        probe = self.http.get(f"{SENASA_BASE}/Sur/Extracciones/List", allow_redirects=False)
        if probe.status_code in (301, 302, 303, 307, 308):
            loc = probe.headers.get("Location", "")
            if "/Login.aspx" in loc:
                return False
        if probe.status_code == 200 and ('name="__VIEWSTATE"' in probe.text or "__VIEWSTATE" in probe.text):
            return True
        return False
