from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from senasa_pipeline.application.ports.http_client_port import HttpClientPort
from senasa_pipeline.application.ports.senasa_login_port import SenasaLoginPort

SENASA_BASE = "https://trazabilidadapicola.senasa.gob.ar"
IDP_HOST = "idp.senasa.gob.ar"
AFIP_BASE = "https://auth.afip.gob.ar"
AFIP_LOGIN_URL = f"{AFIP_BASE}/contribuyente_/login.xhtml?action=SYSTEM&system=senasa_traapi"


class SenasaLoginConsumer(SenasaLoginPort):
    """Login SENASA unificado: AFIP JSF + OIDC en una sola sesión HTTP compartida.

    Replica la estrategia exitosa de coadelpa-project/auth_service.py:
    1. Disparar OIDC con GET a URL protegida
    2. Durante el chase, completar login AFIP JSF cuando llegue a auth.afip.gob.ar
    3. Continuar OIDC hasta volver a SENASA
    4. Seleccionar usuario AFIP si aparece Login.aspx
    """

    def __init__(
        self, http: HttpClientPort, *, cuit: str | None = None, password: str | None = None
    ) -> None:
        self.http = http
        self.cookies: dict[str, str] = {}
        self.cuit = cuit or ""
        self.password = password or ""

    def _log(self, msg: str) -> None:
        print(f"[SenasaLoginConsumer] {msg}")

    # ---------- Helpers genéricos de navegación ----------
    def _auto_submit_first_form(self, html: str, base_url: str):
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
        resp = self.http.post(
            post_url,
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": base_url,
            },
        )
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

    # ---------- Login AFIP JSF completo durante OIDC ----------
    def _complete_afip_jsf_login(self, current_resp) -> object:
        """Completa login AFIP JSF durante el flujo OIDC, igual que coadelpa-project."""
        self._log("Starting AFIP JSF login during OIDC chain")

        # 1. GET inicial de AFIP (ya estamos ahí desde OIDC)
        current = current_resp
        soup = BeautifulSoup(current.text, "html.parser")
        vs = soup.find("input", {"name": "javax.faces.ViewState"})
        f1 = soup.find("form", {"id": "F1"})
        if not vs or not f1:
            self._log("AFIP JSF: missing ViewState or F1 form")
            return current

        view_state = vs.get("value", "")
        action = urljoin(current.url, f1.get("action", ""))

        # 2. POST CUIT
        cuit_payload = {
            "F1": "F1",
            "F1:username": self.cuit,
            "F1:btnSiguiente": "Siguiente",
            "javax.faces.ViewState": view_state,
        }
        resp_cuit = self.http.post(
            action,
            data=cuit_payload,
            headers={
                "Referer": current.url,
                "Origin": AFIP_BASE,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        self._log(f"AFIP CUIT -> {resp_cuit.status_code}")

        # 3. Extraer nuevo ViewState para password
        soup2 = BeautifulSoup(resp_cuit.text, "html.parser")
        vs2 = soup2.find("input", {"name": "javax.faces.ViewState"})
        f1_2 = soup2.find("form", {"id": "F1"})
        if not vs2 or not f1_2:
            self._log("AFIP JSF: missing ViewState or F1 form after CUIT")
            return resp_cuit

        view_state_2 = vs2.get("value", "")
        action_2 = urljoin(resp_cuit.url, f1_2.get("action", ""))

        # 4. POST password
        pwd_payload = {
            "F1": "F1",
            "F1:captcha": "",
            "F1:username": self.cuit,
            "F1:password": self.password,
            "F1:btnIngresar": "Ingresar",
            "javax.faces.ViewState": view_state_2,
        }
        resp_pwd = self.http.post(
            action_2,
            data=pwd_payload,
            headers={
                "Referer": resp_cuit.url,
                "Origin": AFIP_BASE,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        self._log(f"AFIP password -> {resp_pwd.status_code} url={resp_pwd.url}")

        return resp_pwd

    # ---------- Chase completo hasta volver a SENASA ----------
    def _chase_redirects_until_back_on_senasa(self, start_resp, max_hops: int = 50) -> object:
        """Persigue redirects/forms/meta/JS hasta volver a SENASA, completando AFIP JSF si es necesario."""
        current = start_resp
        for i in range(max_hops):
            url_now = current.url or ""
            self._log(f"CHASE[{i}] url={url_now}")

            # Si ya estamos en SENASA (no Login.aspx), terminar
            if url_now.startswith(SENASA_BASE) and "/Login.aspx" not in url_now:
                break

            # Si estamos en AFIP, completar JSF login
            if AFIP_BASE in url_now and "login.xhtml" in url_now:
                current = self._complete_afip_jsf_login(current)
                continue

            # Auto-submit forms
            next_resp = self._auto_submit_first_form(current.text, url_now)
            if next_resp:
                current = next_resp
                continue

            # Meta refresh
            meta_url = self._extract_meta_refresh(current.text, url_now)
            if meta_url:
                current = self.http.get(meta_url)
                continue

            # JS redirect
            js_url = self._extract_js_redirect(current.text, url_now)
            if js_url:
                current = self.http.get(js_url)
                continue

            # Si estamos en IdP, forzar kc_idp_hint
            if IDP_HOST in url_now and "kc_idp_hint" not in url_now:
                sep = "&" if "?" in url_now else "?"
                current = self.http.get(f"{url_now}{sep}kc_idp_hint=AFIP")
                continue

            # Nada más por hacer
            break

        return current

    # ---------- Selección de usuario AFIP en Login.aspx ----------
    def _select_afip_user(self, html: str) -> None:
        """Selecciona usuario AFIP en Login.aspx si aparece la lista de usuarios."""
        soup = BeautifulSoup(html, "html.parser")

        # Extraer campos ocultos
        hidden: dict[str, str] = {}
        for inp in soup.find_all("input", {"type": "hidden", "name": True}):
            hidden[inp["name"]] = inp.get("value", "")
        self._log(f"Hidden fields: {len(hidden)} found")

        # Buscar botón de usuario AFIP
        btn = soup.find("a", string=lambda t: t and "COOP. APICOLA DEL PARANA" in t)
        if not btn:
            # Fallback: primer botón de usuarios AFIP
            cont = soup.find(id=lambda x: x and "rptUsuariosAfip" in x)
            if cont:
                btn = cont.find("a")

        self._log(f"AFIP user button found? {'yes' if btn else 'no'}")
        if not btn:
            return

        btn_id = btn.get("id") or "ctl00_MasterEditBox_ucLogin_rptUsuariosAfip_ctl05_btnLoginAfip"
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

        login_url = f"{SENASA_BASE}/Login.aspx"
        ajax_headers = {
            "Accept": "*/*",
            "x-microsoftajax": "Delta=true",
            "x-requested-with": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": login_url,
        }

        resp_sel = self.http.post(login_url, data=payload, headers=ajax_headers)
        self._log(f"User selection POST -> {resp_sel.status_code}")

        # Continuar chase si hay más redirects
        self._chase_redirects_until_back_on_senasa(resp_sel)

    # ---------- API del puerto ----------
    def login_with_token_sign(self, token: str, sign: str) -> None:
        """Entrada principal: replica _establish_senasa_session_via_idp() de coadelpa-project."""
        if not self.cuit or not self.password:
            raise RuntimeError("CUIT and password are required for unified AFIP+SENASA login")

        # Disparar OIDC navegando a URL protegida
        self._log("Starting unified OIDC+AFIP login flow")
        target = f"{SENASA_BASE}/Sur/Tambores/Consulta"
        resp = self.http.get(target)
        self._log(f"GET {target} -> {resp.status_code} url={resp.url}")

        # Chase completo hasta volver a SENASA
        final_resp = self._chase_redirects_until_back_on_senasa(resp)
        self._log(f"After complete chase -> url={final_resp.url}")

        # Si quedó en Login.aspx, seleccionar usuario AFIP
        if (final_resp.url or "").startswith(SENASA_BASE) and "/Login.aspx" in (
            final_resp.url or ""
        ):
            self._log("Detected Login.aspx, attempting user selection")
            self._select_afip_user(final_resp.text)

        # Guardar cookies
        self.cookies = self.http.dump_cookies()
        self._log(f"Login complete, {len(self.cookies)} cookies saved")

    def validate_session(self) -> bool:
        """Valida que la sesión SENASA esté activa."""
        probe = self.http.get(f"{SENASA_BASE}/Sur/Extracciones/List", allow_redirects=False)
        loc = probe.headers.get("Location", "")
        viewstate_present = ("__VIEWSTATE" in probe.text) or ('name="__VIEWSTATE"' in probe.text)

        self._log(
            f"Validation -> status={probe.status_code} loc={loc[:100]} viewstate={viewstate_present}"
        )

        # Si redirige a Login.aspx, sesión inválida
        if probe.status_code in (301, 302, 303, 307, 308) and "/Login.aspx" in loc:
            return False

        # Si 200 con VIEWSTATE, sesión válida
        if probe.status_code == 200 and viewstate_present:
            return True

        return False
