from __future__ import annotations
from urllib.parse import urljoin
from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from senasa_pipeline.application.ports.http_client_port import HttpClientPort
from senasa_pipeline.application.ports.senasa_login_port import SenasaLoginPort

SENASA_BASE = "https://trazabilidadapicola.senasa.gob.ar"
IDP_HOST = "idp.senasa.gob.ar"

class SenasaLoginConsumer(SenasaLoginPort):
    """Completa login SENASA con token/sign, maneja IdP OIDC y fuerza el flujo iniciando en una URL protegida.

    Estrategia:
      1) POST /afip (token/sign)
      2) Disparar OIDC con GET /Sur/Tambores/Consulta (URL protegida)
      3) Encadenar formularios/meta/JS redirects hasta volver a SENASA
      4) Si aparece Login.aspx con lista de usuarios AFIP, seleccionar
      5) Validar con /Sur/Extracciones/List
    """

    def __init__(self, http: HttpClientPort) -> None:
        self.http = http
        self.cookies: dict[str, str] = {}

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

    def _extract_js_redirect(self, html: str, base_url: str):
        import re
        m = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", html, re.IGNORECASE)
        if not m:
            m = re.search(r"window\.location\s*=\s*['\"]([^'\"]+)['\"]", html, re.IGNORECASE)
        if m:
            return urljoin(base_url, m.group(1))
        return None

    def _chase_until_senasa(self, start_resp, max_hops: int = 20):
        current = start_resp
        for i in range(max_hops):
            url_now = current.url or ''
            self._log(f"CHASE[{i}] url={url_now}")
            # Si ya estamos en SENASA y no es Login.aspx, parar
            if url_now.startswith(SENASA_BASE) and '/Login.aspx' not in url_now:
                break
            # 1) form auto-submit
            next_resp = self._auto_submit_first_form(current.text, url_now)
            if next_resp:
                current = next_resp
                continue
            # 2) meta refresh
            meta_url = self._extract_meta_refresh(current.text, url_now)
            if meta_url:
                current = self.http.get(meta_url)
                continue
            # 3) js redirect
            js_url = self._extract_js_redirect(current.text, url_now)
            if js_url:
                current = self.http.get(js_url)
                continue
            # 4) si estamos en IdP y hay kc_idp_hint faltante, intentar forzarlo
            if IDP_HOST in url_now and 'kc_idp_hint' not in url_now:
                sep = '&' if '?' in url_now else '?'
                current = self.http.get(f"{url_now}{sep}kc_idp_hint=AFIP")
                continue
            # 5) nada más por hacer
            break
        return current

    def _select_user_if_needed(self, html: str, login_url: str) -> None:
        soup = BeautifulSoup(html or '', 'html.parser')
        # Si form intermedio con token/sign
        form = soup.find('form')
        if form and form.find('input', {'name': 'token'}) and form.find('input', {'name': 'sign'}):
            self._log("Detected intermediate AFIP form, auto-submitting")
            action = form.get('action') or login_url
            post_url = urljoin(login_url, action)
            payload = {inp.get('name'): inp.get('value', '') for inp in form.find_all('input') if inp.get('name')}
            resp2 = self.http.post(post_url, data=payload, headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": SENASA_BASE,
                "Referer": f"{SENASA_BASE}/afip",
            })
            self._log(f"Auto-submit -> status={resp2.status_code} url={resp2.url}")
            # recargar login
            page = self.http.get(login_url)
            soup = BeautifulSoup(page.text or '', 'html.parser')
        # hidden fields
        hidden: dict[str, str] = {}
        for inp in soup.find_all('input', {'type': 'hidden', 'name': True}):
            hidden[inp['name']] = inp.get('value', '')
        self._log(f"Hidden keys: {list(hidden.keys())[:6]}... total={len(hidden)}")
        # botón
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
        # perseguir posibles redirecciones extra
        self._chase_until_senasa(resp_post)

    def login_with_token_sign(self, token: str, sign: str) -> None:
        # 1) POST /afip
        self._log("Posting token/sign to /afip")
        headers = {
            'Origin': 'https://portalcf.cloud.afip.gob.ar',
            'Referer': 'https://portalcf.cloud.afip.gob.ar/portal/app/',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        r_afip = self.http.post(f"{SENASA_BASE}/afip", data={'token': token, 'sign': sign}, headers=headers, allow_redirects=True)
        self._log(f"/afip -> status={r_afip.status_code} url={r_afip.url}")
        # 2) Disparar OIDC directamente con URL protegida
        protected = self.http.get(f"{SENASA_BASE}/Sur/Tambores/Consulta")
        self._log(f"GET /Sur/Tambores/Consulta -> status={protected.status_code} url={protected.url}")
        last = self._chase_until_senasa(protected)
        self._log(f"After chase -> url={last.url}")
        # 3) Si aún en Login.aspx, intentar selección de usuario
        if (last.url or '').startswith(SENASA_BASE) and '/Login.aspx' in (last.url or ''):
            self._select_user_if_needed(last.text, f"{SENASA_BASE}/Login.aspx?from=afip")
        # 4) cookies
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
