from __future__ import annotations
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from senasa_pipeline.application.ports.http_client_port import HttpClientPort
from senasa_pipeline.application.ports.senasa_login_port import SenasaLoginPort
import time

SENASA_BASE = "https://trazabilidadapicola.senasa.gob.ar"
SENASA_IDP = "https://idp.senasa.gob.ar"

class SenasaLoginConsumer(SenasaLoginPort):
    """Consume token/sign AFIP para establecer sesión SENASA.
    
    Responsabilidades:
    1. POST token/sign a /afip
    2. GET/Login.aspx?from=afip y auto-submit si corresponde
    3. Selección de usuario AFIP (AJAX __EVENTTARGET)
    4. Completar posibles formularios/meta refresh posteriores (desde resp_post)
    5. Manejar flujo OIDC/Keycloak si es necesario
    6. Validar sesión final DESPUÉS del follow-up completo
    """

    def __init__(self, http: HttpClientPort) -> None:
        self.http = http
        self.cookies: dict[str, str] = {}
        self._session_ready = False  # Flag to track if session setup is complete

    def _log(self, msg: str) -> None:
        print(f"[SenasaLoginConsumer] {msg}")

    def _log_response_details(self, resp, step_name: str) -> None:
        """Log detailed response information for debugging."""
        url = getattr(resp, 'url', 'unknown')
        domain = urlparse(str(url)).netloc if url != 'unknown' else 'unknown'
        content_length = len(resp.text) if hasattr(resp, 'text') else 0
        
        self._log(f"{step_name} -> status={resp.status_code} url={url}")
        self._log(f"{step_name} -> domain={domain} content_len={content_length}")
        
        # Log if we're in OIDC territory
        if 'idp.senasa.gob.ar' in str(url):
            self._log(f"{step_name} -> DETECTED OIDC IdP response")
        
        # Log forms present
        if hasattr(resp, 'text') and resp.text:
            soup = BeautifulSoup(resp.text, 'html.parser')
            forms = soup.find_all('form')
            self._log(f"{step_name} -> found {len(forms)} form(s)")
            
            for i, form in enumerate(forms):
                method = form.get('method', 'get').upper()
                action = form.get('action', '')
                inputs = len(form.find_all('input'))
                self._log(f"{step_name} -> form[{i}]: {method} {action} ({inputs} inputs)")
                
                # Log OIDC-specific form details
                if 'Login.aspx' in action:
                    code_input = form.find('input', {'name': 'code'})
                    state_input = form.find('input', {'name': 'state'})
                    if code_input or state_input:
                        self._log(f"{step_name} -> form[{i}]: DETECTED OIDC callback form")

    def _auto_submit_first_form(self, html: str, base_url: str):
        soup = BeautifulSoup(html, 'html.parser')
        form = soup.find('form')
        if not form:
            return None
        action = form.get('action') or ''
        if not action:
            return None
        post_url = urljoin(base_url, action)
        payload = {inp.get('name'): inp.get('value', '') for inp in form.find_all('input') if inp.get('name')}
        
        self._log(f"Auto-submitting form to {post_url} with {len(payload)} fields")
        resp = self.http.post(post_url, data=payload, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": base_url,
        })
        self._log_response_details(resp, "Auto-form-submit")
        return resp

    def _extract_meta_refresh(self, html: str, base_url: str):
        soup = BeautifulSoup(html, 'html.parser')
        meta = soup.find('meta', attrs={'http-equiv': lambda v: v and v.lower() == 'refresh'})
        if not meta:
            return None
        content = meta.get('content', '')
        parts = content.split('url=', 1)
        if len(parts) == 2:
            url = parts[1].strip().strip("'\"")
            full_url = urljoin(base_url, url)
            self._log(f"Meta refresh detected: {full_url}")
            return full_url
        return None

    def login_with_token_sign(self, token: str, sign: str) -> None:
        self._log("Starting SENASA login with AFIP token/sign")
        self._session_ready = False  # Reset session ready flag
        
        # 1) POST /afip
        afip_url = f"{SENASA_BASE}/afip"
        headers = {
            "Referer": "https://portalcf.cloud.afip.gob.ar/portal/app/",
            "Origin": "https://portalcf.cloud.afip.gob.ar",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        resp_afip = self.http.post(afip_url, data={"token": token, "sign": sign}, headers=headers, allow_redirects=True)
        self._log_response_details(resp_afip, "POST-afip")
        
        # 2) GET Login.aspx?from=afip o usar HTML de /afip
        login_url = f"{SENASA_BASE}/Login.aspx?from=afip"
        html = resp_afip.text or ''
        if not html or len(html) < 100:
            self._log("Getting Login.aspx?from=afip explicitly")
            resp_login = self.http.get(login_url, allow_redirects=False)
            self._log_response_details(resp_login, "GET-login-aspx")
            html = resp_login.text or ''
        
        # 3) Selección usuario + follow-up COMPLETO
        self._log("Starting user selection and follow-up")
        resp_post = self._select_afip_user_and_complete_follow_up(html, login_url)
        
        # 4) Guardar cookies
        self.cookies = self.http.dump_cookies()
        self._session_ready = True
        self._log(f"Login complete, {len(self.cookies)} cookies saved, session ready")

    def _select_afip_user_and_complete_follow_up(self, initial_html: str, login_url: str):
        soup = BeautifulSoup(initial_html, 'html.parser')
        
        # Auto-submit si hay form intermedio con token/sign
        form = soup.find('form')
        if form and form.find('input', {'name': 'token'}) and form.find('input', {'name': 'sign'}):
            self._log("Found intermediate form with token/sign, auto-submitting")
            action = form.get('action') or login_url
            post_url = urljoin(login_url, action)
            payload = {inp.get('name'): inp.get('value', '') for inp in form.find_all('input') if inp.get('name')}
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": SENASA_BASE,
                "Referer": f"{SENASA_BASE}/afip",
            }
            resp2 = self.http.post(post_url, data=payload, headers=headers)
            self._log_response_details(resp2, "Token-sign-form")
            soup = BeautifulSoup(resp2.text, 'html.parser')
        
        # Hidden fields
        hidden: dict[str, str] = {}
        for inp in soup.find_all('input', {'type': 'hidden', 'name': True}):
            hidden[inp['name']] = inp.get('value', '')
        self._log(f"Hidden fields found: {len(hidden)}")
        
        # Botón usuario
        btn = soup.find('a', id='ctl00_MasterEditBox_ucLogin_rptUsuariosAfip_ctl05_btnLoginAfip')
        if not btn:
            btn = soup.find('a', string=lambda t: t and 'COOP. APICOLA DEL PARANA' in t)
        if not btn:
            cont = soup.find(id=lambda x: x and 'rptUsuariosAfip' in x)
            if cont:
                btn = cont.find('a')
        self._log(f"AFIP user button found? {'yes' if btn else 'no'}")
        if not btn:
            self._log("ERROR: Could not find AFIP user button")
            return None
        
        btn_id = btn.get('id', 'ctl00_MasterEditBox_ucLogin_rptUsuariosAfip_ctl05_btnLoginAfip')
        event_target = btn_id.replace('_', '$')
        
        payload = hidden.copy()
        payload.update({
            'ctl00$ScriptManager1': f"ctl00$updatePanelEdit|{event_target}",
            '__EVENTTARGET': event_target,
            '__EVENTARGUMENT': '',
            '__ASYNCPOST': 'true',
        })
        payload.setdefault('__LASTFOCUS', '')
        payload.setdefault('__SCROLLPOSITIONX', '0')
        payload.setdefault('__SCROLLPOSITIONY', '0')
        payload.setdefault('ctl00$hiddenPendingDownload', '')
        
        ajax_headers = {
            'Accept': '*/*',
            'x-microsoftajax': 'Delta=true',
            'x-requested-with': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Referer': login_url,
        }
        
        self._log(f"Posting user selection with payload keys: {list(payload.keys())}")
        resp_post = self.http.post(login_url, data=payload, headers=ajax_headers)
        self._log_response_details(resp_post, "User-selection-POST")
        
        # Follow-up completo
        current = resp_post
        follow_up_completed = False
        
        self._log("Starting follow-up sequence...")
        # 1. Procesar todos los formularios y meta refresh posibles
        for i in range(8):
            self._log(f"Follow-up iteration {i+1}/8")
            self._log_response_details(current, f"Follow-up-iter-{i+1}")
            
            # Check if we're at IdP
            current_url = getattr(current, 'url', '')
            if 'idp.senasa.gob.ar' in str(current_url):
                self._log(f"Follow-up-iter-{i+1} -> We're at OIDC IdP, checking for callback form")
                oidc_resp = self._handle_oidc_callback_if_present(current)
                if oidc_resp:
                    current = oidc_resp
                    self._log_response_details(current, f"OIDC-callback-handled")
                    continue
            
            # Try auto-submit form
            next_resp = self._auto_submit_first_form(current.text, login_url)
            if next_resp:
                current = next_resp
                self._log(f"Follow-up form {i+1} submitted")
                continue
                
            # Try meta refresh
            meta_url = self._extract_meta_refresh(current.text, login_url)
            if meta_url:
                self._log(f"Following meta refresh to: {meta_url}")
                current = self.http.get(meta_url)
                self._log_response_details(current, f"Meta-refresh-{i+1}")
                continue
                
            # No more follow-ups needed
            follow_up_completed = True
            self._log(f"Follow-up completed at iteration {i+1}")
            break
        
        if not follow_up_completed:
            self._log("Follow-up sequence reached max iterations")
        
        # 2. Pausa breve
        self._log("Pausing for session stabilization...")
        time.sleep(0.5)
        
        # 3. Final probe
        self._log("Performing final probe...")
        try:
            probe_url = f"{SENASA_BASE}/Sur/Tambores/Consulta"
            probe = self.http.get(probe_url, allow_redirects=True)
            self._log_response_details(probe, "Final-probe")
            
            probe_final_url = getattr(probe, 'url', '')
            if 'idp.senasa.gob.ar' in str(probe_final_url):
                self._log("Final probe ended at OIDC IdP - session not established")
            elif '/Login.aspx' in str(probe_final_url):
                self._log("Final probe redirected to login - session failed")  
            else:
                self._log("Final probe successful - session should be ready")
                
        except Exception as e:
            self._log(f"Final probe failed: {e}")
        
        return current

    def _handle_oidc_callback_if_present(self, response):
        """Handle OIDC callback form submission if present."""
        if not hasattr(response, 'text') or not response.text:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for form posting to Login.aspx
        callback_form = None
        for form in soup.find_all('form'):
            action = form.get('action', '')
            method = form.get('method', 'get').lower()
            if method == 'post' and 'Login.aspx' in action:
                callback_form = form
                break
        
        if not callback_form:
            self._log("No OIDC callback form found")
            return None
        
        # Extract form data
        action = callback_form.get('action')
        payload = {}
        for inp in callback_form.find_all('input'):
            name = inp.get('name')
            value = inp.get('value', '')
            if name:
                payload[name] = value
        
        self._log(f"Found OIDC callback form: {action}")
        self._log(f"OIDC form payload keys: {list(payload.keys())}")
        
        # Submit the callback form
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": str(getattr(response, 'url', '')),
            "Origin": SENASA_IDP,
        }
        
        try:
            callback_resp = self.http.post(action, data=payload, headers=headers)
            self._log_response_details(callback_resp, "OIDC-callback-submit")
            return callback_resp
        except Exception as e:
            self._log(f"OIDC callback submit failed: {e}")
            return None

    def validate_session(self) -> bool:
        """Valida sesión SENASA. Solo debe llamarse DESPUÉS del follow-up completo."""
        if not self._session_ready:
            self._log("WARNING: validate_session called before session setup completed")
            return False
            
        url = f"{SENASA_BASE}/Sur/Extracciones/List"
        self._log(f"Validating session at: {url}")
        
        # Allow redirects but check final URL to detect login redirects
        resp = self.http.get(url, allow_redirects=True, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{SENASA_BASE}/",
        })
        
        self._log_response_details(resp, "Session-validation")
        
        # Check final URL and content
        final_url = str(getattr(resp, 'url', ''))
        
        # Failed validations
        if 'idp.senasa.gob.ar' in final_url:
            self._log("Validation failed: redirected to OIDC IdP")
            return False
            
        if '/Login.aspx' in final_url:
            self._log("Validation failed: redirected to login page")
            return False
            
        # Check for viewstate in the response
        viewstate_present = 'name="__VIEWSTATE"' in resp.text
        
        success = resp.status_code == 200 and viewstate_present
        self._log(f"Validation result: status={resp.status_code} viewstate={viewstate_present} success={success}")
        
        return success