from __future__ import annotations
from urllib.parse import urljoin
from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from senasa_pipeline.application.ports.http_client_port import HttpClientPort
from senasa_pipeline.application.ports.senasa_login_port import SenasaLoginPort

SENASA_BASE = "https://trazabilidadapicola.senasa.gob.ar"
IDP_HOST = "idp.senasa.gob.ar"
AFIP_BASE = "https://auth.afip.gob.ar"
AFIP_LOGIN_URL = f"{AFIP_BASE}/contribuyente_/login.xhtml?action=SYSTEM&system=senasa_traapi"

class SenasaLoginConsumer(SenasaLoginPort):
    """Completa login SENASA integrando OIDC (IdP) y login AFIP JSF in-situ."""

    def __init__(self, http: HttpClientPort, *, cuit: str | None = None, password: str | None = None) -> None:
        self.http = http
        self.cookies: dict[str, str] = {}
        self.cuit = cuit or ""
        self.password = password or ""

    def _log(self, msg: str) -> None:
        print(f"[SenasaLoginConsumer] {msg}")

    # ---------- Helpers genéricos de navegación ----------
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

    def _extract_js_redirect(self, html: str, base_url: str):
        import re
        m = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", html, re.IGNORECASE)
        if not m:
            m = re.search(r"window\.location\s*=\s*['\"]([^'\"]+)['\"]", html, re.IGNORECASE)
        if m:
            return urljoin(base_url, m.group(1))
        return None

    # ---------- Login AFIP (JSF) embebido ----------
    def _afip_get_initial(self):
        r = self.http.get(AFIP_LOGIN_URL, headers={
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-User": "?1",
        })
        soup = BeautifulSoup(r.text, 'html.parser')
        vs = soup.find('input', {'name': 'javax.faces.ViewState'})
        f1 = soup.find('form', {'id': 'F1'})
        if not vs or not f1 or not f1.get('action'):
            raise RuntimeError("AFIP JSF inline: no ViewState/action inicial")
        return vs.get('value', ''), urljoin(AFIP_LOGIN_URL, f1['action'])

    def _afip_post_cuit(self, view_state: str, action_url: str):
        payload = {
            'F1': 'F1',
            'F1:username': self.cuit,
            'F1:btnSiguiente': 'Siguiente',
            'javax.faces.ViewState': view_state,
        }
        headers = {
            "Referer": AFIP_LOGIN_URL,
            "Origin": AFIP_BASE,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        r = self.http.post(action_url, data=payload, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        vs2 = soup.find('input', {'name': 'javax.faces.ViewState'})
        f1 = soup.find('form', {'id': 'F1'})
        if not vs2 or not f1 or not f1.get('action'):
            raise RuntimeError("AFIP JSF inline: no ViewState/action de password")
        return vs2.get('value', ''), urljoin(action_url, f1['action'])

    def _afip_post_password(self, view_state_pwd: str, action_url: str, *, referer: str):
        payload = {
            'F1': 'F1',
            'F1:captcha': '',
            'F1:username': self.cuit,
            'F1:password': self.password,
            'F1:btnIngresar': 'Ingresar',
            'javax.faces.ViewState': view_state_pwd,
        }
        headers = {
            "Referer": referer,
            "Origin": AFIP_BASE,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        r = self.http.post(action_url, data=payload, headers=headers)
        # No necesitamos token/sign aquí: el IdP continuará la cadena
        return r

    def _complete_afip_login_inline(self):
        if not self.cuit or not self.password:
            raise RuntimeError("AFIP JSF inline: faltan CUIT/password para completar OIDC")
        vs, act1 = self._afip_get_initial()
        vs2, act2 = self._afip_post_cuit(vs, act1)
        self._afip_post_password(vs2, act2, referer=act1)

    # ---------- Perseguir OIDC hasta volver a SENASA ----------
    def _chase_until_senasa(self, start_resp, max_hops: int = 30):
        current = start_resp
        for i in range(max_hops):
            url_now = current.url or ''
            self._log(f"CHASE[{i}] url={url_now}")
            # si ya estamos en SENASA (no Login.aspx), parar
            if url_now.startswith(SENASA_BASE) and '/Login.aspx' not in url_now:
                break
            # form auto-submit
            next_resp = self._auto_submit_first_form(current.text, url_now)
            if next_resp:
                current = next_resp
                continue
            # meta refresh
            meta_url = self._extract_meta_refresh(current.text, url_now)
            if meta_url:
                current = self.http.get(meta_url)
                continue
            # js redirect
            js_url = self._extract_js_redirect(current.text, url_now)
            if js_url:
                current = self.http.get(js_url)
                continue
            # si estamos en IdP, forzar kc_idp_hint
            if IDP_HOST in url_now and 'kc_idp_hint' not in url_now:
                sep = '&' if '?' in url_now else '?'
                current = self.http.get(f"{url_now}{sep}kc_idp_hint=AFIP")
                continue
            # si seguimos en IdP sin más pasos, ejecutar login AFIP inline y refrescar
            if IDP_HOST in url_now:
                self._log("Inline AFIP login on IdP chain")
                self._complete_afip_login_inline()
                # tras login, intentar nuevamente
                current = self.http.get(url_now)
                continue
            break
        return current

    # ---------- Selección de usuario AFIP en Login.aspx (si aparece) ----------
    def _select_user_if_needed(self, html: str, login_url: str) -> None:
        soup = BeautifulSoup(html or '', 'html.parser')
        # hidden
        hidden: dict[str, str] = {}
        for inp in soup.find_all('input', {'type': 'hidden', 'name': True}):
            hidden[inp['name']] = inp.get('value', '')
        self._log(f"Hidden keys: {list(hidden.keys())[:6]}... total={len(hidden)}")
        # botón usuario
        btn = soup.find('a', id='ctl00_MasterEditBox_ucLogin_rptUsuariosAfip_ctl05_btnLoginAfip')
        if not btn:
            btn = soup.find('a', string=lambda t: t and 'COOP. APICOLA DEL PARANA' in t)
        self._log(f"AFIP user button found? {'yes' if btn else 'no'}")
        if not btn:
            return
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
        self._log(f"POST selection -> status={resp_post.status_code} url={resp_post.url}")
        self._chase_until_senasa(resp_post)

    # ---------- API del puerto ----------
    def login_with_token_sign(self, token: str, sign: str) -> None:
        # En el flujo OIDC completo, el POST /afip no es estrictamente necesario, pero se mantiene por compatibilidad
        self._log("Posting token/sign to /afip (compat)")
        headers = {
            'Origin': 'https://portalcf.cloud.afip.gob.ar',
            'Referer': 'https://portalcf.cloud.afip.gob.ar/portal/app/',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        self.http.post(f"{SENASA_BASE}/afip", data={'token': token, 'sign': sign}, headers=headers, allow_redirects=True)
        # Disparar OIDC directamente con URL protegida
        protected = self.http.get(f"{SENASA_BASE}/Sur/Tambores/Consulta")
        self._log(f"GET /Sur/Tambores/Consulta -> status={protected.status_code} url={protected.url}")
        last = self._chase_until_senasa(protected)
        self._log(f"After chase -> url={last.url}")
        # Si aún estamos en Login.aspx, intentar selección de usuario
        if (last.url or '').startswith(SENASA_BASE) and '/Login.aspx' in (last.url or ''):
            self._select_user_if_needed(last.text, f"{SENASA_BASE}/Login.aspx?from=afip")
        # cookies
        self.cookies = self.http.dump_cookies()
        self._log(f"Cookies after login: {len(self.cookies)} keys")

    def validate_session(self) -> bool:
        probe = self.http.get(f"{SENASA_BASE}/Sur/Extracciones/List", allow_redirects=False)
        loc = probe.headers.get('Location', '')
        viewstate_present = ('name="__VIEWSTATE"' in probe.text) or ('__VIEWSTATE' in probe.text)
        self._log(f"Probe -> status={probe.status_code} loc={loc[:140]} viewstate={viewstate_present}")
        if probe.status_code in (301,302,303,307,308) and '/Login.aspx' in loc:
            return False
        if probe.status_code == 200 and viewstate_present:
            return True
        return False
