from __future__ import annotations
from typing import Protocol

class SenasaLoginPort(Protocol):
    """Consumes AFIP token/sign and completes SENASA login (including user selection)."""

    def login_with_token_sign(self, token: str, sign: str) -> None: ...
    def validate_session(self) -> bool: ...
