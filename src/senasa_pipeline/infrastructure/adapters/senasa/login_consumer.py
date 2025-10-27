from __future__ import annotations

import re
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup  # type: ignore[import-untyped]

from senasa_pipeline.application.ports.http_client_port import HttpClientPort
from senasa_pipeline.application.ports.senasa_login_port import SenasaLoginPort

SENASA_BASE = "https://trazabilidadapicola.senasa.gob.ar"
SENASA_IDP = "https://idp.senasa.gob.ar"


class SenasaLoginConsumer(SenasaLoginPort):
    """Consume token/sign AFIP para establecer sesión SENASA.
    Maneja formularios, meta refresh y flujo OIDC (Keycloak) con logs detallados.
    """

    def __init__(self, http: HttpClientPort) -> None:
        self.http = http
        self.cookies: dict[str, str] = {}
        self._session_ready = False
        self._dump_html = True  # activar para inspección temporal
        self._max_dump_chars = 3000

    def _log(self, msg: str) -> None:
        print(f"[SenasaLoginConsumer] {msg}")

    def _dump_snippet(self, html: str, label: str) -> None:
        if not self._dump_html or not html:
            return
        # Sanitiza nuevas líneas para que el log sea legible
        snippet = re.sub(r"\s+", " ", html)[: self._max_dump_chars]
        self._log(f"{label} HTML snippet: {snippet}")

    def _log_response_details(self, resp, step_name: str) -> None:
        url = getattr(resp, "url", "unknown")
        domain = urlparse(str(url)).netloc if url != "unknown" else "unknown"
        content_length = len(resp.text) if hasattr(resp, "text") else 0
        self._log(f"{step_name} -> status={resp.status_code} url={url}")
        self._log(f"{step_name} -> domain={domain} content_len={content_length}")
        if "idp.senasa.gob.ar" in str(url):
            self._log(f"{step_name} -> DETECTED OIDC IdP response")
        if hasattr(resp, "text") and resp.text:
            soup = BeautifulSoup(resp.text, "html.parser")
            forms = soup.find_all("form")
            self._log(f"{step_name} -> found {len(forms)} form(s)")
            for i, form in enumerate(forms):
                method = form.get("method", "get").upper()
                action = form.get("action", "")
                inputs = len(form.find_all("input"))
                self._log(f"{step_name} -> form[{i}]: {method} {action} ({inputs} inputs)")
                if "Login.aspx" in action:
                    code_input = form.find("input", {"name": "code"})
                    state_input = form.find("input", {"name": "state"})
                    if code_input or state_input:
                        self._log(f"{step_name} -> form[{i}]: DETECTED OIDC callback form")
        # Dump pequeño de HTML para inspección
        self._dump_snippet(getattr(resp, "text", ""), f"{step_name}")

    def _auto_submit_first_form(self, html: str, base_url: str):
        """Auto-submit the first form found in the HTML"""
        soup = BeautifulSoup(html, "html.parser")
        form = soup.find("form")
        if not form:
            return None
        action = form.get("action") or ""
        if not action:
            return None
        post_url = urljoin(base_url, action)
        payload = {
            inp.get("name"): inp.get("value", "")
            for inp in form.find_all("input")
            if inp.get("name")
        }
        self._log(f"Auto-submitting form to {post_url} with {len(payload)} fields")
        resp = self.http.post(
            post_url,
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": base_url,
            },
        )
        self._log_response_details(resp, "Auto-form-submit")
        return resp

    def _extract_meta_refresh(self, html: str, base_url: str):
        soup = BeautifulSoup(html, "html.parser")
        meta = soup.find("meta", attrs={"http-equiv": lambda v: v and v.lower() == "refresh"})
        if not meta:
            return None
        content = meta.get("content", "")
        parts = content.split("url=", 1)
        if len(parts) == 2:
            url = parts[1].strip().strip("'\"")
            full_url = urljoin(base_url, url)
            self._log(f"Meta refresh detected: {full_url}")
            return full_url
        return None

    def login_with_token_sign(self, token: str, sign: str) -> None:
        self._log("Starting SENASA login with AFIP token/sign")
        self._session_ready = False
        afip_url = f"{SENASA_BASE}/afip"
        headers = {
            "Referer": "https://portalcf.cloud.afip.gob.ar/portal/app/",
            "Origin": "https://portalcf.cloud.afip.gob.ar",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        resp_afip = self.http.post(
            afip_url, data={"token": token, "sign": sign}, headers=headers, allow_redirects=True
        )
        self._log_response_details(resp_afip, "POST-afip")
        login_url = f"{SENASA_BASE}/Login.aspx?from=afip"
        html = resp_afip.text or ""
        if not html or len(html) < 100:
            self._log("Getting Login.aspx?from=afip explicitly")
            resp_login = self.http.get(login_url, allow_redirects=False)
            self._log_response_details(resp_login, "GET-login-aspx")
            html = resp_login.text or ""
        self._log("Starting user selection and follow-up")
        self._select_afip_user_and_complete_follow_up(html, login_url)
        self._assert_senasa_session()
        self.cookies = self.http.dump_cookies()
        self._log(f"Login complete, {len(self.cookies)} cookies saved, session ready")

    def _select_afip_user_and_complete_follow_up(self, initial_html: str, login_url: str):
        html = initial_html
        soup = BeautifulSoup(html, "html.parser")
        form = soup.find("form")
        if form and form.find("input", {"name": "token"}) and form.find("input", {"name": "sign"}):
            self._log("Found intermediate form with token/sign, auto-submitting")
            action = form.get("action") or login_url
            post_url = urljoin(login_url, action)
            payload = {
                inp.get("name"): inp.get("value", "")
                for inp in form.find_all("input")
                if inp.get("name")
            }
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": SENASA_BASE,
                "Referer": f"{SENASA_BASE}/afip",
            }
            resp2 = self.http.post(post_url, data=payload, headers=headers)
            self._log_response_details(resp2, "Token-sign-form")
            soup = BeautifulSoup(resp2.text, "html.parser")
        hidden: dict[str, str] = {}
        for inp in soup.find_all("input", {"type": "hidden", "name": True}):
            hidden[inp["name"]] = inp.get("value", "")
        self._log(f"Hidden fields found: {len(hidden)}")
        btn = soup.find("a", id="ctl00_MasterEditBox_ucLogin_rptUsuariosAfip_ctl05_btnLoginAfip")
        if not btn:
            btn = soup.find("a", string=lambda t: t and "COOP. APICOLA DEL PARANA" in t)
        if not btn:
            cont = soup.find(id=lambda x: x and "rptUsuariosAfip" in x)
            if cont:
                btn = cont.find("a")
        self._log(f"SENASA user button found? {'yes' if btn else 'no'}")
        if not btn:
            self._log("ERROR: Could not find SENASA user button")
            return None
        btn_id = btn.get("id", "ctl00_MasterEditBox_ucLogin_rptUsuariosAfip_ctl05_btnLoginAfip")
        event_target = btn_id.replace("_", "$")
        payload = hidden.copy()
        payload.update(
            {
                "ctl00$ScriptManager1": f"ctl00$updatePanelEdit|{event_target}",
                "__EVENTTARGET": event_target,
                "__EVENTARGUMENT": "",
                "__ASYNCPOST": "true",
            }
        )
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
        self._log(f"Posting user selection with payload keys: {list(payload.keys())}")
        resp_post = self.http.post(login_url, data=payload, headers=ajax_headers)
        self._log_response_details(resp_post, "User-selection-POST")
        self._log("Starting follow-up sequence...")
        for _ in range(8):
            next_resp = self._auto_submit_first_form(resp_post.text, base_url=login_url)
            if next_resp is None:
                meta_url = self._extract_meta_refresh(resp_post.text, base_url=login_url)
                if meta_url:
                    resp_post = self.http.get(meta_url)
                    continue
                break
            resp_post = next_resp
        time.sleep(0.5)
        return resp_post



    def validate_session(self) -> bool:
        if not self._session_ready:
            self._log("WARNING: validate_session called before session setup completed")
            return False
        url = f"{SENASA_BASE}/Sur/Extracciones/List"
        self._log(f"Validating session at: {url}")
        resp = self.http.get(
            url,
            allow_redirects=True,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": f"{SENASA_BASE}/",
            },
        )
        self._log_response_details(resp, "Session-validation")
        final_url = str(getattr(resp, "url", ""))
        if "idp.senasa.gob.ar" in final_url:
            self._log("Validation failed: redirected to OIDC IdP")
            return False
        if "/Login.aspx" in final_url:
            self._log("Validation failed: redirected to login page")
            return False
        viewstate_present = 'name="__VIEWSTATE"' in resp.text
        success = resp.status_code == 200 and viewstate_present
        self._log(
            f"Validation result: status={resp.status_code} viewstate={viewstate_present} success={success}"
        )
        return success

    def _assert_senasa_session(self)->None:
        url=f"{SENASA_BASE}/Sur/Extracciones/List"
        resp=self.http.get(url,allow_redirects=True,headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{SENASA_BASE}/",
        })
        if resp.status_code in (301,302,303,307,308):
            loc=resp.headers.get("Location","")
            if '/Login.aspx' in loc:
                self._log("Session not found")
                raise RuntimeError("Session not found")
        if resp.status_code == 200 and 'name="__VIEWSTATE"' not in resp.text:
            self._log("This page dont´s have a viewstate, Session not found")
            raise RuntimeError("Session not found")
        self._session_ready=True
        self._log("Session ready")
