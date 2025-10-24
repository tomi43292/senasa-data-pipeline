from __future__ import annotations
from urllib.parse import urljoin
from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from senasa_pipeline.application.ports.http_client_port import HttpClientPort
from senasa_pipeline.application.ports.senasa_login_port import SenasaLoginPort
import time

SENASA_BASE = "https://trazabilidadapicola.senasa.gob.ar"

class SenasaLoginConsumer(SenasaLoginPort):
    """Consume token/sign AFIP para establecer sesión SENASA.
    
    Responsabilidades:
    1. POST token/sign a /afip
    2. GET/Login.aspx?from=afip y auto-submit si corresponde
    3. Selección de usuario AFIP (AJAX __EVENTTARGET)
    4. Completar posibles formularios/meta refresh posteriores (desde resp_post)
    5. Validar sesión final DESPUÉS del follow-up completo
    """

    def __init__(self, http: HttpClientPort) -> None:
        self.http = http
        self.cookies: dict[str, str] = {}
        self._session_ready = False  # Flag to track if session setup is complete

    def _log(self, msg: str) -> None:
        print(f"[SenasaLoginConsumer] {msg}")

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
        resp = self.http.post(post_url, data=payload, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": base_url,
        })
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
            return urljoin(base_url, url)
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
        self._log(f"POST /afip -> status={resp_afip.status_code} len={len(resp_afip.text)}")
        
        # 2) GET Login.aspx?from=afip o usar HTML de /afip
        login_url = f"{SENASA_BASE}/Login.aspx?from=afip"
        html = resp_afip.text or ''
        if not html or len(html) < 100:
            resp_login = self.http.get(login_url, allow_redirects=False)
            html = resp_login.text or ''
        
        # 3) Selección usuario + follow-up COMPLETO como coadelpa-project
        resp_post = self._select_afip_user_and_complete_follow_up(html, login_url)
        
        # 4) Guardar cookies - la sesión debe estar lista ahora
        self.cookies = self.http.dump_cookies()
        self._session_ready = True  # Mark session as ready after complete follow-up
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
        resp_post = self.http.post(login_url, data=payload, headers=ajax_headers)
        self._log(f"User selection POST -> status={resp_post.status_code}")
        
        # CRITICAL: Follow-up completo ANTES de cualquier validación
        # Esto replica el comportamiento de coadelpa-project funcional
        current = resp_post
        follow_up_completed = False
        
        # 1. Procesar todos los formularios y meta refresh posibles
        for i in range(8):
            next_resp = self._auto_submit_first_form(current.text, login_url)
            if next_resp:
                current = next_resp
                self._log(f"Follow-up form {i+1} submitted -> status={current.status_code}")
                continue
            meta_url = self._extract_meta_refresh(current.text, login_url)
            if meta_url:
                current = self.http.get(meta_url)
                self._log(f"Follow-up meta refresh {i+1} -> status={current.status_code}")
                continue
            # No more follow-ups needed
            follow_up_completed = True
            break
        
        if follow_up_completed:
            self._log("Follow-up sequence completed successfully")
        else:
            self._log("Follow-up sequence reached max iterations")
        
        # 2. Pausa breve para permitir que el servidor procese el estado de sesión
        time.sleep(0.5)
        
        # 3. CRITICAL: Follow redirects in final probe to complete authentication
        # This is where the session actually gets established
        try:
            probe = self.http.get(f"{SENASA_BASE}/Sur/Tambores/Consulta", allow_redirects=True)
            self._log(f"Final probe after follow-up -> status={probe.status_code} final_url={probe.url}")
            
            # If we got redirected back to login, the session isn't ready yet
            if '/Login.aspx' in str(probe.url):
                self._log("Final probe redirected to login - session not fully established yet")
            else:
                self._log("Final probe successful - session should be ready")
                
        except Exception as e:
            self._log(f"Final probe failed (non-critical): {e}")
        
        return current

    def validate_session(self) -> bool:
        """Valida sesión SENASA. Solo debe llamarse DESPUÉS del follow-up completo."""
        if not self._session_ready:
            self._log("WARNING: validate_session called before session setup completed")
            return False
            
        url = f"{SENASA_BASE}/Sur/Extracciones/List"
        
        # Allow redirects but check final URL to detect login redirects
        resp = self.http.get(url, allow_redirects=True, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{SENASA_BASE}/",
        })
        
        # Check if we got redirected to login page
        final_url = str(resp.url) if hasattr(resp, 'url') else ''
        if '/Login.aspx' in final_url:
            self._log(f"Validation redirected to login: {final_url}")
            return False
            
        # Check for viewstate in the response
        viewstate_present = 'name="__VIEWSTATE"' in resp.text
        
        self._log(f"Validation -> status={resp.status_code} final_url={final_url} viewstate={viewstate_present}")
        
        # Valid session: 200 status AND viewstate present AND not on login page
        return resp.status_code == 200 and viewstate_present and '/Login.aspx' not in final_url
