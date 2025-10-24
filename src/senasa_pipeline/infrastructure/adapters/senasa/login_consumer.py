from __future__ import annotations
from urllib.parse import urljoin
from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from senasa_pipeline.application.ports.http_client_port import HttpClientPort
from senasa_pipeline.application.ports.senasa_login_port import SenasaLoginPort

SENASA_BASE = "https://trazabilidadapicola.senasa.gob.ar"

class SenasaLoginConsumer(SenasaLoginPort):
    """Consume token/sign AFIP para establecer sesión SENASA.
    
    Replica exactamente _post_token_sign_to_senasa() y _select_afip_user() 
    de coadelpa-project/auth_service.py, pero como adaptador separado.
    
    Responsabilidades:
    1. POST token/sign a /afip
    2. GET Login.aspx?from=afip
    3. Auto-submit si hay form intermedio con token/sign
    4. Seleccionar usuario AFIP (por id o texto)
    5. Validar sesión final con __VIEWSTATE
    """

    def __init__(self, http: HttpClientPort) -> None:
        self.http = http
        self.cookies: dict[str, str] = {}

    def _log(self, msg: str) -> None:
        print(f"[SenasaLoginConsumer] {msg}")

    def _auto_submit_first_form(self, html: str, base_url: str):
        """Auto-submit primer form encontrado para avanzar en flujos."""
        soup = BeautifulSoup(html, 'html.parser')
        form = soup.find('form')
        if not form:
            return None
        
        action = form.get('action')
        if not action:
            return None
        
        url = urljoin(base_url, action)
        payload = {}
        for inp in form.find_all('input', {'name': True}):
            payload[inp['name']] = inp.get('value', '')
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded", 
            "Referer": base_url
        }
        
        return self.http.post(url, data=payload, headers=headers)

    def _extract_meta_refresh(self, html: str, base_url: str):
        """Extrae URL de meta refresh."""
        soup = BeautifulSoup(html, 'html.parser')
        meta = soup.find('meta', attrs={'http-equiv': lambda v: v and v.lower() == 'refresh'})
        if not meta:
            return None
        
        content = meta.get('content', '')
        parts = content.split('url=', 1)
        if len(parts) == 2:
            url = parts[1].strip().strip('"\'')
            return urljoin(base_url, url)
        
        return None

    def login_with_token_sign(self, token: str, sign: str) -> None:
        """Completa login SENASA usando token/sign de AFIP."""
        self._log("Starting SENASA login with AFIP token/sign")
        
        # 1. POST token/sign a /afip
        afip_url = f"{SENASA_BASE}/afip"
        headers = {
            "Referer": "https://portalcf.cloud.afip.gob.ar/portal/app/",
            "Origin": "https://portalcf.cloud.afip.gob.ar",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        resp_afip = self.http.post(afip_url, data={"token": token, "sign": sign}, headers=headers, allow_redirects=True)
        self._log(f"POST /afip -> status={resp_afip.status_code} len={len(resp_afip.text)}")
        
        # 2. GET Login.aspx?from=afip
        login_url = f"{SENASA_BASE}/Login.aspx?from=afip"
        
        # Usar HTML de respuesta /afip si es útil, sino hacer GET explícito
        html = resp_afip.text or ''
        if not html or len(html) < 100:
            resp_login = self.http.get(login_url, allow_redirects=False)
            html = resp_login.text or ''
        
        self._select_afip_user(html, login_url)
        
        # Guardar cookies
        self.cookies = self.http.dump_cookies()
        self._log(f"Login complete, {len(self.cookies)} cookies saved")

    def _select_afip_user(self, html: str, login_url: str) -> None:
        """Selecciona usuario AFIP en Login.aspx si es necesario."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Auto-submit si hay form intermedio con token/sign
        form = soup.find('form')
        if form and form.find('input', {'name': 'token'}) and form.find('input', {'name': 'sign'}):
            self._log("Found intermediate form with token/sign, auto-submitting")
            action = form.get('action') or login_url
            post_url = urljoin(login_url, action)
            
            payload = {}
            for inp in form.find_all('input', {'name': True}):
                payload[inp['name']] = inp.get('value', '')
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": SENASA_BASE,
                "Referer": f"{SENASA_BASE}/afip",
            }
            
            resp2 = self.http.post(post_url, data=payload, headers=headers)
            soup = BeautifulSoup(resp2.text, 'html.parser')
        
        # Extraer hidden fields para selección de usuario
        hidden: dict[str, str] = {}
        for inp in soup.find_all('input', {'type': 'hidden', 'name': True}):
            hidden[inp['name']] = inp.get('value', '')
        
        self._log(f"Hidden fields found: {len(hidden)}")
        
        # Buscar botón de usuario AFIP
        btn = soup.find('a', id='ctl00_MasterEditBox_ucLogin_rptUsuariosAfip_ctl05_btnLoginAfip')
        if not btn:
            btn = soup.find('a', string=lambda t: t and 'COOP. APICOLA DEL PARANA' in t)
        if not btn:
            # Fallback: primer anchor en contenedor de usuarios AFIP
            cont = soup.find(id=lambda x: x and 'rptUsuariosAfip' in x)
            if cont:
                btn = cont.find('a')
        
        self._log(f"AFIP user button found? {'yes' if btn else 'no'}")
        if not btn:
            return  # No hay selección requerida
        
        btn_id = btn.get('id', 'ctl00_MasterEditBox_ucLogin_rptUsuariosAfip_ctl05_btnLoginAfip')
        event_target = btn_id.replace('_', '$')
        
        # Construir payload para selección AJAX
        payload = hidden.copy()
        payload.update({
            "ctl00$ScriptManager1": f"ctl00$updatePanelEdit|{event_target}",
            "__EVENTTARGET": event_target,
            "__EVENTARGUMENT": "",
            "__ASYNCPOST": "true",
        })
        
        # Campos comunes ASP.NET
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
        self._log(f"User selection POST -> status={resp_post.status_code}")
        
        # Completar posibles auto-submit/meta refresh posteriores
        current_resp = resp_post
        for _ in range(8):
            next_resp = self._auto_submit_first_form(current_resp.text, login_url)
            if next_resp is None:
                meta_url = self._extract_meta_refresh(current_resp.text, login_url)
                if meta_url:
                    current_resp = self.http.get(meta_url)
                    continue
                break
            current_resp = next_resp

    def validate_session(self) -> bool:
        """Valida que la sesión SENASA esté activa."""
        url = f"{SENASA_BASE}/Sur/Extracciones/List"
        resp = self.http.get(url, allow_redirects=False, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{SENASA_BASE}/",
        })
        
        # Si redirige a Login.aspx, sesión inválida
        if resp.status_code in (301, 302, 303, 307, 308):
            loc = resp.headers.get('Location', '')
            self._log(f"Validation redirect to: {loc}")
            if '/Login.aspx' in loc:
                return False
        
        # Si 200 con __VIEWSTATE, sesión válida
        viewstate_present = 'name="__VIEWSTATE"' in resp.text
        self._log(f"Validation -> status={resp.status_code} viewstate={viewstate_present}")
        
        return resp.status_code == 200 and viewstate_present
