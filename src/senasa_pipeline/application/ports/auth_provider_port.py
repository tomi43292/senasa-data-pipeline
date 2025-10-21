from __future__ import annotations

from typing import Protocol


class AuthProviderPort(Protocol):
    """Obtains AFIP token/sign to be consumed by SENASA /afip."""

    def get_token_sign(self) -> tuple[str, str]:
        """Returns (token, sign). Raises exceptions on failure."""
        ...
