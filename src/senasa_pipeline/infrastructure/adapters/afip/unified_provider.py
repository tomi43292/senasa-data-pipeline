from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup  # type: ignore[import-untyped]

from senasa_pipeline.application.ports.afip_token_provider_port import AfipTokenProviderPort
from senasa_pipeline.application.ports.http_client_port import HttpClientPort

AFIP_BASE_URL = "https://auth.afip.gob.ar"
AFIP_LOGIN_URL = f"{AFIP_BASE_URL}/contribuyente_/login.xhtml?action=SYSTEM&system=senasa_traapi"
PORTAL_CF_BASE = "https://portalcf.cloud.afip.gob.ar"


class UnifiedAfipProvider(AfipTokenProviderPort):
    """Obtiene token/sign de AFIP usando JSF primero, fallback a Portal CF.

    1. AFIP JSF: CUIT → password → extraer token/sign de myform
    2. Si no hay token/sign, Portal CF: /portal/app → /api/servicios → /api/autorizacion

    Comparte HttpClientPort con SenasaLoginConsumer para mantener sesión unificada.
    """

    def __init__(self, http: HttpClientPort, *, cuit: str, password: str) -> None:
        self.http = http
        self.cuit = cuit
        self.password = password

    def _log(self, msg: str) -> None:
        print(f"[UnifiedAfipProvider] {msg}")

    # ---------- AFIP JSF Login ----------
    def _get_initial_afip_cuit_page(self) -> tuple[str, str]:
        """GET inicial a AFIP JSF para extraer ViewState y action."""
        resp = self.http.get(
            AFIP_LOGIN_URL,
            headers={
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "cross-site",
                "Sec-Fetch-User": "?1",
            },
        )

        soup = BeautifulSoup(resp.text, "html.parser")
        view_state_input = soup.find("input", {"name": "javax.faces.ViewState"})
        form_f1 = soup.find("form", {"id": "F1"})

        if not view_state_input or not form_f1 or not form_f1.get("action"):
            raise RuntimeError("AFIP JSF: No se pudo extraer ViewState o action inicial")

        action_url = urljoin(AFIP_LOGIN_URL, form_f1["action"])
        return view_state_input.get("value", ""), action_url

    def _post_cuit(self, view_state_cuit: str, action_url: str) -> tuple[str, str]:
        """POST CUIT a AFIP JSF para obtener nuevo ViewState y action."""
        payload = {
            "F1": "F1",
            "F1:username": self.cuit,
            "F1:btnSiguiente": "Siguiente",
            "javax.faces.ViewState": view_state_cuit,
        }

        headers = {
            "Referer": AFIP_LOGIN_URL,
            "Origin": AFIP_BASE_URL,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        resp = self.http.post(action_url, data=payload, headers=headers)
        soup = BeautifulSoup(resp.text, "html.parser")

        view_state_pwd = soup.find("input", {"name": "javax.faces.ViewState"})
        form_f1 = soup.find("form", {"id": "F1"})

        if not view_state_pwd or not form_f1 or not form_f1.get("action"):
            raise RuntimeError("AFIP JSF: No se pudo extraer ViewState o action de password")

        action_pwd = urljoin(action_url, form_f1["action"])
        return view_state_pwd.get("value", ""), action_pwd

    def _post_password(
        self, view_state_pwd: str, action_url: str, *, referer: str
    ) -> tuple[str, str, str]:
        """POST password a AFIP JSF, intenta extraer token/sign de myform."""
        payload = {
            "F1": "F1",
            "F1:captcha": "",
            "F1:username": self.cuit,
            "F1:password": self.password,
            "F1:btnIngresar": "Ingresar",
            "javax.faces.ViewState": view_state_pwd,
        }

        headers = {
            "Referer": referer,
            "Origin": AFIP_BASE_URL,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        resp = self.http.post(action_url, data=payload, headers=headers)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Buscar form myform con token/sign
        form = soup.find("form", {"name": "myform"}) or soup.find("form")
        if not form:
            return "", "", ""

        magyp_action = form.get("action")
        token_input = form.find("input", {"name": "token"})
        sign_input = form.find("input", {"name": "sign"})

        if (
            not magyp_action
            or not token_input
            or not token_input.get("value")
            or not sign_input
            or not sign_input.get("value")
        ):
            return "", "", ""

        return magyp_action, token_input.get("value", ""), sign_input.get("value", "")

    # ---------- Portal CF Fallback ----------
    def _portal_open_app(self) -> None:
        """Abre Portal CF /app para inicializar sesión."""
        self.http.get(
            f"{PORTAL_CF_BASE}/portal/app/",
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            },
        )

    def _portal_get_service_info(self) -> dict[str, object]:
        """GET servicio info con reintentos si no hay JSON directo."""
        url = f"{PORTAL_CF_BASE}/portal/api/servicios/{self.cuit}/servicio/senasa_traapi"

        resp = self.http.get(
            url,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": f"{PORTAL_CF_BASE}/portal/app/",
                "X-Requested-With": "XMLHttpRequest",
            },
        )

        try:
            return resp.json()
        except Exception:
            # Reintento tras navegar a /portal/app y /portal/servicios
            self.http.get(f"{PORTAL_CF_BASE}/portal/app/")
            self.http.get(f"{PORTAL_CF_BASE}/portal/servicios")

            resp2 = self.http.get(
                url,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Referer": f"{PORTAL_CF_BASE}/portal/app/",
                },
            )

            try:
                return resp2.json()
            except Exception:
                return {}

    def _portal_get_authorization(self) -> tuple[str, str]:
        """GET token/sign de autorización con reintentos."""
        url = (
            f"{PORTAL_CF_BASE}/portal/api/servicios/{self.cuit}/servicio/senasa_traapi/autorizacion"
        )

        resp = self.http.get(
            url,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": f"{PORTAL_CF_BASE}/portal/app/",
                "X-Requested-With": "XMLHttpRequest",
            },
        )

        try:
            data = resp.json()
        except Exception:
            # Reintento tras /portal/servicios
            self.http.get(f"{PORTAL_CF_BASE}/portal/servicios")

            resp2 = self.http.get(
                url,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Referer": f"{PORTAL_CF_BASE}/portal/app/",
                },
            )
            data = resp2.json()

        if not data or "token" not in data or "sign" not in data:
            raise RuntimeError("Portal CF: no se obtuvo token/sign de autorización para SENASA")

        return data["token"], data["sign"]

    # ---------- API del puerto ----------
    def get_token_sign(self) -> tuple[str, str]:
        """Obtiene token/sign: AFIP JSF primero, fallback a Portal CF."""
        self._log("Starting AFIP JSF login")

        try:
            # Flujo AFIP JSF
            view_state_cuit, action_url_cuit = self._get_initial_afip_cuit_page()
            view_state_pwd, action_url_pwd = self._post_cuit(view_state_cuit, action_url_cuit)
            magyp_action, token_afip, sign_afip = self._post_password(
                view_state_pwd, action_url_pwd, referer=action_url_cuit
            )

            if token_afip and sign_afip:
                self._log("AFIP JSF login successful, got token/sign")
                return token_afip, sign_afip

            self._log("AFIP JSF: no token/sign in response, falling back to Portal CF")

        except Exception as e:
            self._log(f"AFIP JSF failed: {e}, falling back to Portal CF")

        # Fallback a Portal CF
        self._log("Starting Portal CF fallback")

        self._portal_open_app()
        service_info = self._portal_get_service_info()

        if (
            not service_info
            or service_info.get("servicio", {}).get("serviceName") != "senasa_traapi"
        ):
            raise RuntimeError("Portal CF: servicio senasa_traapi no disponible para el CUIT")
        self._log(f"Portal CF fallback successful {service_info}, got token/sign")
        token, sign = self._portal_get_authorization()
        self._log("Portal CF fallback successful, got token/sign")

        return token, sign
