from __future__ import annotations
from typing import Tuple
from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from senasa_pipeline.application.ports.http_client_port import HttpClientPort
from senasa_pipeline.application.ports.auth_provider_port import AuthProviderPort

class PortalCFProvider(AuthProviderPort):
    """Obtiene token/sign desde Portal CF de AFIP (camino preferente)."""

    BASE = "https://portalcf.cloud.afip.gob.ar/portal"

    def __init__(self, http: HttpClientPort, cuit: str) -> None:
        self.http = http
        self.cuit = cuit

    def get_token_sign(self) -> Tuple[str, str]:
        # Abrir app para establecer cookies
        self.http.get(f"{self.BASE}/app/", headers={"Accept": "text/html,application/xhtml+xml"})
        # Tocar servicios y luego API de servicio
        self.http.get(f"{self.BASE}/servicios")
        resp = self.http.get(f"{self.BASE}/api/servicios/{self.cuit}/servicio/senasa_traapi", headers={"Accept": "application/json"})
        # Intentar autorizacion directa
        auth = self.http.get(f"{self.BASE}/api/servicios/{self.cuit}/servicio/senasa_traapi/autorizacion", headers={"Accept": "application/json"})
        try:
            import json
            data = json.loads(auth.text)
        except Exception:
            # fallback: a veces responde HTML intermedio; reintentar tras refrescar app
            self.http.get(f"{self.BASE}/app/")
            auth = self.http.get(f"{self.BASE}/api/servicios/{self.cuit}/servicio/senasa_traapi/autorizacion", headers={"Accept": "application/json"})
            import json
            data = json.loads(auth.text)
        token = data.get("token")
        sign = data.get("sign")
        if not token or not sign:
            raise RuntimeError("AFIP Portal: token/sign no disponibles")
        return token, sign
