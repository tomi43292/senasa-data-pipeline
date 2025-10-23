from __future__ annotations
from urllib.parse import urljoin
from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from senasa_pipeline.application.ports.http_client_port import HttpClientPort
from senasa_pipeline.application.ports.senasa_login_port import SenasaLoginPort

SENASA_BASE = "https://trazabilidadapicola.senasa.gob.ar"

class SenasaLoginConsumer(SenasaLoginPort):
    def __init__(self, http: HttpClientPort) -> None:
        self.http = http
        self.cookies: dict[str, str] = {}

    def _log(self, msg: str) -> None:
        # Simple print-based debug; can be replaced by structlog later
        print(f"[SenasaLoginConsumer] {msg}")

    def login_with_token_sign(self, token: str, sign: str) -> None:
        self._log("Posting token/sign to /afip")
        headers = {
            "Origin": "https://portalcf.cloud.afip.gob.ar",
            "Referer": "https://portalcf.cloud.afip.gob.ar/portal/app/",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        resp_afip = self.http.post(f"{SENASA_BASE}/afip", data={"token": token, "sign": sign}, headers=headers, allow_redirects=True)
        self._log(f"/afip -> status={resp_afip.status_code} url={resp_afip.url}")

        login_url = f"{SENASA_BASE}/Login.aspx?from=afip"
        resp = self.http.get(login_url, allow_redirects=True)
        self._log(f"GET Login.aspx -> status={resp.status_code} url={resp.url}")
        html = resp.text or ""
        soup = BeautifulSoup(html, "html.parser")

        form = soup.find("form")
        if form and form.find("input", {"name": "token"}) and form.find("input", {"name": "sign"}):
            self._log("Detected intermediate form with token/sign, auto-submitting")
            action = form.get("action") or login_url
            post_url = urljoin(login_url, action)
            payload = {inp.get("name"): inp.get("value", "") for inp in form.find_all("input") if inp.get("name")}
            resp2 = self.http.post(post_url, data=payload, headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": SENASA_BASE,
                "Referer": f"{SENASA_BASE}/afip",
            })
            self._log(f"Auto-submit -> status={resp2.status_code} url={resp2.url}")
            resp = self.http.get(login_url)
            self._log(f"Reload Login.aspx -> status={resp.status_code} url={resp.url}")
            soup = BeautifulSoup(resp.text or "", "html.parser")

        hidden: dict[str, str] = {}
        for inp in soup.find_all("input", {"type": "hidden", "name": True}):
            hidden[inp["name"]] = inp.get("value", "")
        self._log(f"Hidden keys: {list(hidden.keys())[:6]}... total={len(hidden)}")

        btn = soup.find('a', id='ctl00_MasterEditBox_ucLogin_rptUsuariosAfip_ctl05_btnLoginAfip')
        if not btn:
            btn = soup.find('a', string=lambda t: t and 'COOP. APICOLA DEL PARANA' in t)
        self._log(f"AFIP user button found? {'yes' if btn else 'no'}")

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
            resp_post = self.http.post(login_url, data=payload, headers=ajax_headers)
            self._log(f"POST selection -> status={resp_post.status_code} url={resp_post.url}")

        self.cookies = self.http.dump_cookies()
        self._log(f"Cookies after login: {len(self.cookies)} keys")

    def validate_session(self) -> bool:
        probe = self.http.get(f"{SENASA_BASE}/Sur/Extracciones/List", allow_redirects=False)
        loc = probe.headers.get("Location", "")
        viewstate_present = ('name="__VIEWSTATE"' in probe.text) or ("__VIEWSTATE" in probe.text)
        self._log(f"Probe -> status={probe.status_code} loc={loc[:120]} viewstate={viewstate_present}")
        if probe.status_code in (301,302,303,307,308) and "/Login.aspx" in loc:
            return False
        if probe.status_code == 200 and viewstate_present:
            return True
        return False
