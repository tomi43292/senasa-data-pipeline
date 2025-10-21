from __future__ import annotations
from typing import Tuple
import json
from senasa_pipeline.application.ports.http_client_port import HttpClientPort
from senasa_pipeline.application.ports.auth_provider_port import AuthProviderPort

class PortalCFProvider(AuthProviderPort):
    """Obtiene token/sign desde Portal CF de AFIP (camino preferente) con detección de no-JSON y reintentos suaves."""

    BASE = "https://portalcf.cloud.afip.gob.ar/portal"

    def __init__(self, http: HttpClientPort, cuit: str) -> None:
        self.http = http
        self.cuit = cuit

    def _touch_portal(self) -> None:
        self.http.get(f"{self.BASE}/app/", headers={"Accept": "text/html,application/xhtml+xml"})
        self.http.get(f"{self.BASE}/servicios", headers={"Accept": "text/html,application/xhtml+xml"})
        self.http.get(
            f"{self.BASE}/api/servicios/{self.cuit}/servicio/senasa_traapi",
            headers={"Accept": "application/json", "Referer": f"{self.BASE}/app/"},
        )

    def _get_autorizacion(self):
        return self.http.get(
            f"{self.BASE}/api/servicios/{self.cuit}/servicio/senasa_traapi/autorizacion",
            headers={
                "Accept": "application/json, text/plain, */*",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{self.BASE}/app/",
            },
        )

    def get_token_sign(self) -> Tuple[str, str]:
        # Primer intento
        self._touch_portal()
        auth = self._get_autorizacion()
        content_type = (auth.headers.get("Content-Type") or "").lower()
        if "application/json" not in content_type:
            # Reintento suave tras refrescar portal
            self._touch_portal()
            auth = self._get_autorizacion()
            content_type = (auth.headers.get("Content-Type") or "").lower()
        try:
            data = json.loads(auth.text)
        except Exception:
            snippet = auth.text[:200].replace("\n", " ")
            raise RuntimeError(f"AFIP Portal: respuesta no JSON en /autorizacion (CT={content_type}) snippet='{snippet}'")
        token = data.get("token")
        sign = data.get("sign")
        if not token or not sign:
            raise RuntimeError("AFIP Portal: token/sign no disponibles en respuesta JSON")
        return token, sign
