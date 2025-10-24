from __future__ import annotations
from typing import Protocol, Tuple

class AfipTokenProviderPort(Protocol):
    """Puerto de aplicación para obtener credenciales AFIP (token, sign).

    Implementaciones posibles:
    - UnifiedAfipProvider (JSF + Portal CF fallback)
    - Mocks/Fakes para testing
    """

    def get_token_sign(self) -> Tuple[str, str]:
        """Retorna (token, sign) para autenticación en SENASA.
        
        Debe levantar excepciones significativas en caso de error (red, credenciales inválidas, etc.).
        """
        ...
