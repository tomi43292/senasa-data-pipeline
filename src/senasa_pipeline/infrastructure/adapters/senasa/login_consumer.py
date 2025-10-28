from __future__ import annotations

from mimetypes import init
import re
import time
from urllib.parse import urljoin, urlparse, unquote

from bs4 import BeautifulSoup  # type: ignore[import-untyped]

from senasa_pipeline.application.ports.http_client_port import HttpClientPort
from senasa_pipeline.application.ports.senasa_login_port import SenasaLoginPort

SENASA_BASE = "https://trazabilidadapicola.senasa.gob.ar"


class SenasaLoginConsumer(SenasaLoginPort):
    """
    Consume token/sign AFIP para establecer sesión SENASA.
    """

    def __init__(self, http: HttpClientPort) -> None:
        self.http = http
        self.cookies: dict[str, str] = {}
        self._session_ready = False
        self._dump_html = True
        self._max_dump_chars = 2000

    def _log(self, msg: str) -> None:
        print(f"[SenasaLoginConsumer] {msg}")

    def _dump_snippet(self, html: str, label: str) -> None:
        if not self._dump_html or not html:
            return
        snippet = re.sub(r"\s+", " ", html)[: self._max_dump_chars]
        self._log(f"{label} snippet: {snippet}")

    def _log_response_details(self, resp, step_name: str) -> None:
        url = getattr(resp, "url", "unknown")
        content_length = len(resp.text) if hasattr(resp, "text") else 0
        self._log(f"{step_name} -> status={resp.status_code} len={content_length} url={url}")
        if hasattr(resp, "text") and resp.text:
            soup = BeautifulSoup(resp.text, "html.parser")
            forms = soup.find_all("form")
            viewstate = 'name="__VIEWSTATE"' in resp.text
            self._log(f"{step_name} -> forms={len(forms)} viewstate={viewstate}")
        if content_length < 500:  # Log short responses completely
            self._dump_snippet(getattr(resp, "text", ""), step_name)

    def _parse_updatepanel_response(self, response_text: str) -> str | None:
        """Parse Microsoft AJAX UpdatePanel response for pageRedirect."""
        if not response_text or not response_text.startswith("1|#|"):
            return None
        parts = response_text.split("|")
        try:
            for i, part in enumerate(parts):
                if part == "pageRedirect" and i + 2 < len(parts):
                    redirect_url = parts[i + 2]
                    return unquote(redirect_url) if "%" in redirect_url else redirect_url
        except Exception as e:
            self._log(f"Error parsing UpdatePanel: {e}")
        return None

    def _follow_updatepanel_redirect(self, response, base_url: str):
        """Follow UpdatePanel pageRedirect if present."""
        if not hasattr(response, "text"):
            return None
        redirect_path = self._parse_updatepanel_response(response.text)
        if not redirect_path:
            return None
        redirect_url = f"{SENASA_BASE}{redirect_path}" if redirect_path.startswith("/") else urljoin(base_url, redirect_path)
        self._log(f"Following UpdatePanel redirect to: {redirect_url}")
        try:
            return self.http.get(redirect_url, headers={
                "Referer": base_url,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            })
        except Exception as e:
            self._log(f"Error following UpdatePanel redirect: {e}")
            return None

    def _auto_submit_first_form(self, html: str, base_url: str):
        """Auto-submit first form found in HTML."""
        soup = BeautifulSoup(html, "html.parser")
        form = soup.find("form")
        if not form:
            return None
        action = form.get("action") or ""
        if not action:
            return None
        post_url = urljoin(base_url, action)
        payload = {inp.get("name"): inp.get("value", "") for inp in form.find_all("input") if inp.get("name")}
        return self.http.post(post_url, data=payload, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": base_url,
        })

    def _extract_meta_refresh(self, html: str, base_url: str):
        """Extract meta refresh URL from HTML."""
        soup = BeautifulSoup(html, "html.parser")
        meta = soup.find("meta", attrs={"http-equiv": lambda v: v and v.lower() == "refresh"})
        if not meta:
            return None
        content = meta.get("content", "")
        parts = content.split("url=", 1)
        if len(parts) == 2:
            url = parts[1].strip().strip("'\"")
            return urljoin(base_url, url)
        return None

    def login_with_token_sign(self, token: str, sign: str) -> None:
        self._log("Starting SENASA login with AFIP token/sign")
        self._session_ready = False
        
        # 1. POST token/sign to SENASA
        html=self._post_token_sign_to_senasa(token, sign)
        
        # 2. Get login page and select user
        self._select_user_and_establish_session(html)
        
        # 3. Save cookies
        self.cookies = self.http.dump_cookies()
        self._session_ready = True
        self._log(f"Login complete, {len(self.cookies)} cookies saved")

    def _post_token_sign_to_senasa(self, token: str, sign: str) -> str:
        """Step 1: POST token/sign to /afip endpoint."""
        url = f"{SENASA_BASE}/afip"
        headers = {
            "Referer": "https://portalcf.cloud.afip.gob.ar/portal/app/",
            "Origin": "https://portalcf.cloud.afip.gob.ar",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        resp = self.http.post(url, data={"token": token, "sign": sign}, headers=headers, allow_redirects=True)
        self._log_response_details(resp, "POST-afip")
        return resp.text

    def _select_user_and_establish_session(self,initial_html: str | None = None) -> None:
        """Step 2: Navigate to login page, select user, and establish session."""
        login_url = f"{SENASA_BASE}/Login.aspx?from=afip"
        html=initial_html or ''
        # GET login page with user selection
        if not html:
            resp = self.http.get(login_url, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{SENASA_BASE}/afip",
            },allow_redirects=False)
            self._log_response_details(resp, "GET-login-page")
        
        # Handle intermediate token/sign form if present
        soup = BeautifulSoup(html, "html.parser")
        form = soup.find("form")
        if form and form.find("input", {"name": "token"}) and form.find("input", {"name": "sign"}):
            self._log("Auto-submitting intermediate token/sign form")
            action = form.get("action") or login_url
            post_url = urljoin(login_url, action)
            payload = {inp.get("name"): inp.get("value", "") for inp in form.find_all("input") if inp.get("name")}
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": SENASA_BASE,
                "Referer": f"{SENASA_BASE}/afip",
            }
            resp = self.http.post(post_url, data=payload, headers=headers)
            self._log_response_details(resp, "Token-sign-auto-submit")
            soup = BeautifulSoup(resp.text, "html.parser")
        
        # Extract hidden fields
        hidden = {}
        for inp in soup.find_all("input", {"type": "hidden", "name": True}):
            hidden[inp["name"]] = inp.get("value", "")
        self._log(f"Extracted {len(hidden)} hidden fields")
        
        # Find COOP. APICOLA DEL PARANA button - robust detection
        user_btn = None
        # Try by exact ID first
        user_btn = soup.find("a", id="ctl00_MasterEditBox_ucLogin_rptUsuariosAfip_ctl05_btnLoginAfip")
        if not user_btn:
            # Try by text content
            user_btn = soup.find("a", string=lambda t: t and "COOP. APICOLA DEL PARANA" in t)
        if not user_btn:
            # Try finding any button with the CUIT
            user_btn = soup.find("a", string=lambda t: t and "30-70933844-3" in t)
        if not user_btn:
            # Fallback: find in repeater container
            container = soup.find(id=lambda x: x and "rptUsuariosAfip" in x)
            if container:
                buttons = container.find_all("a")
                for btn in buttons:
                    if btn.get_text() and "COOP. APICOLA DEL PARANA" in btn.get_text():
                        user_btn = btn
                        break
        
        if not user_btn:
            raise RuntimeError("Could not find COOP. APICOLA DEL PARANA user button")
        
        btn_id = user_btn.get('id', 'ctl00_MasterEditBox_ucLogin_rptUsuariosAfip_ctl05_btnLoginAfip')
        if not btn_id:
            raise RuntimeError("User button has no ID")
        
        self._log(f"Found user button: {btn_id} -> {user_btn.get_text()}")
        
        # Execute user selection AJAX POST with exact DevTools headers
        event_target = btn_id.replace("_", "$")
        payload = hidden.copy()
        payload.update({
            "ctl00$ScriptManager1": f"ctl00$updatePanelEdit|{event_target}",
            "__EVENTTARGET": event_target,
            "__EVENTARGUMENT": "",
            "__ASYNCPOST": "true",
            "__LASTFOCUS": "",
            "__SCROLLPOSITIONX": "0",
            "__SCROLLPOSITIONY": "0", 
            "ctl00$hiddenPendingDownload": "",
            "ctl00$hidden_PENDING_DOWNLOAD_FILENAME": "",
            "ctl00$hidden_PENDING_DOWNLOAD_CONTENTTYPE": "",
            "ctl00$hidden_PENDING_DOWNLOAD_BYTES": "",
            "ctl00$hiddenPostBackAction": "",
        })
        
        # Exact headers from DevTools
        ajax_headers = {
            "Accept": "*/*",
            "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": SENASA_BASE,
            "Referer": login_url,
            "X-MicrosoftAjax": "Delta=true",
            "X-Requested-With": "XMLHttpRequest",
        }
        
        self._log(f"Executing user selection AJAX POST with {len(payload)} fields")
        resp_ajax = self.http.post(login_url, data=payload, headers=ajax_headers)
        self._log_response_details(resp_ajax, "User-selection-AJAX")
        
        """# Handle response
        if hasattr(resp_ajax, 'text') and resp_ajax.text.strip():
            # Non-empty response - check for UpdatePanel redirect
            if resp_ajax.text.startswith('1|#|'):
                redirect_path = self._parse_updatepanel_response(resp_ajax.text)
                if redirect_path:
                    self._log(f"UpdatePanel redirect to: {redirect_path}")
                    # Follow redirect and log error details
                    error_resp = self._follow_updatepanel_redirect(resp_ajax, login_url)
                    if error_resp:
                        self._log_response_details(error_resp, "Error-page")
                    raise RuntimeError(f"User selection failed - redirected to: {redirect_path}")
            else:
                self._log("Non-empty AJAX response (unexpected):")
                self._dump_snippet(resp_ajax.text, "AJAX-unexpected")
        else:
            self._log("AJAX response empty/null (success indicator)")"""
        
        # Navigate to Default.aspx like the browser does
        self._log("Navigating to /Default.aspx to establish session")
        default_resp = self.http.get(f"{SENASA_BASE}/Default.aspx", allow_redirects=False, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": login_url,
        })
        self._log_response_details(default_resp, f"Default-aspx status-code {default_resp.status_code} ")
        
        # Verify we got to the main app page
        if default_resp.status_code != 200:
            if default_resp.status_code in (301, 302, 303, 307, 308):
                loc = default_resp.headers.get('Location', '')
                if '/Login.aspx' in loc:
                    raise RuntimeError("Default.aspx redirected to login - session not established")
                else:
                    self._log(f"Default.aspx redirected to: {loc}")
            else:
                raise RuntimeError(f"Default.aspx returned {default_resp.status_code}")
        
        
        self._log("Session established successfully at /Default.aspx")

    # ---------- Helpers ----------
    def _follow_updatepanel_redirect(self, response, base_url: str):
        """Follow UpdatePanel pageRedirect."""
        if not hasattr(response, "text"):
            return None
        redirect_path = self._parse_updatepanel_response(response.text)
        if not redirect_path:
            return None
        redirect_url = f"{SENASA_BASE}{redirect_path}" if redirect_path.startswith("/") else urljoin(base_url, redirect_path)
        try:
            return self.http.get(redirect_url, headers={
                "Referer": base_url,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            })
        except Exception as e:
            self._log(f"Error following UpdatePanel redirect: {e}")
            return None

    # ---------- Validation ----------
    def validate_session(self) -> bool:
        """Validate SENASA session without following redirects."""
        if not self._session_ready:
            self._log("WARNING: validate_session called before session setup")
            return False
        
        url = f"{SENASA_BASE}/Sur/Extracciones/List"
        resp = self.http.get(url, allow_redirects=False, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{SENASA_BASE}/Default.aspx",
        })
        self._log_response_details(resp, "Session-validation")
        
        if resp.status_code in (301, 302, 303, 307, 308):
            loc = resp.headers.get('Location', '')
            if '/Login.aspx' in loc:
                self._log("Validation failed: redirected to login")
                return False
        
        success = resp.status_code == 200 and 'name="__VIEWSTATE"' in resp.text
        self._log(f"Validation result: status={resp.status_code} viewstate={success} success={success}")
        return success