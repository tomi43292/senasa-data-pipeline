from __future__ import annotations
from typing import Tuple, Mapping
from urllib.parse import urljoin
from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from senasa_pipeline.application.ports.http_client_port import HttpClientPort
from senasa_pipeline.application.ports.auth_provider_port import AuthProviderPort

AFIP_BASE = "https://auth.afip.gob.ar"
AFIP_LOGIN_URL = f"{AFIP_BASE}/contribuyente_/login.xhtml?action=SYSTEM&system=senasa_traapi"

class JSFProvider(AuthProviderPort):
    """Proveedor AFIP (JSF clásico) para obtener token/sign mediante CUIT + password.

    Flujo:
      1) GET login.xhtml → extrae javax.faces.ViewState y action del form F1
      2) POST CUIT → obtiene nuevo ViewState/action para contraseña
      3) POST password → busca form (myform) con hidden inputs token/sign
    """

    def __init__(self, http: HttpClientPort, cuit: str, password: str) -> None:
        self.http = http
        self.cuit = cuit
        self.password = password

    def get_token_sign(self) -> Tuple[str, str]:
        view_state_cuit, action_cuit = self._get_initial_afip_cuit_page()
        view_state_pwd, action_pwd = self._post_cuit(view_state_cuit, action_cuit)
        token, sign = self._post_password(view_state_pwd, action_pwd, referer=action_cuit)
        if not token or not sign:
            raise RuntimeError("AFIP JSF: no se pudo obtener token/sign tras login")
        return token, sign

    def _get_initial_afip_cuit_page(self) -> Tuple[str, str]:
        resp = self.http.get(AFIP_LOGIN_URL, headers={
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-User": "?1",
        })
        soup = BeautifulSoup(resp.text, "html.parser")
        view_state_input = soup.find('input', {'name': 'javax.faces.ViewState'})
        form_f1 = soup.find('form', {'id': 'F1'})
        if not view_state_input or not form_f1 or not form_f1.get('action'):
            raise RuntimeError("AFIP JSF: no se pudo extraer ViewState/action inicial")
        action_url = urljoin(AFIP_LOGIN_URL, form_f1['action'])
        return view_state_input.get('value', ''), action_url

    def _post_cuit(self, view_state_cuit: str, action_url: str) -> Tuple[str, str]:
        payload = {
            'F1': 'F1',
            'F1:username': self.cuit,
            'F1:btnSiguiente': 'Siguiente',
            'javax.faces.ViewState': view_state_cuit,
        }
        headers = {
            "Referer": AFIP_LOGIN_URL,
            "Origin": AFIP_BASE,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        resp = self.http.post(action_url, data=payload, headers=headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        view_state_pwd = soup.find('input', {'name': 'javax.faces.ViewState'})
        form_f1 = soup.find('form', {'id': 'F1'})
        if not view_state_pwd or not form_f1 or not form_f1.get('action'):
            raise RuntimeError("AFIP JSF: no se pudo extraer ViewState/action de contraseña")
        action_pwd = urljoin(action_url, form_f1['action'])
        return view_state_pwd.get('value', ''), action_pwd

    def _post_password(self, view_state_pwd: str, action_url: str, *, referer: str) -> Tuple[str, str]:
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
        resp = self.http.post(action_url, data=payload, headers=headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        form = soup.find('form', {'name': 'myform'}) or soup.find('form')
        if not form:
            return "", ""
        token_inp = form.find('input', {'name': 'token'})
        sign_inp = form.find('input', {'name': 'sign'})
        token = token_inp.get('value', '') if token_inp else ''
        sign = sign_inp.get('value', '') if sign_inp else ''
        return token, sign
