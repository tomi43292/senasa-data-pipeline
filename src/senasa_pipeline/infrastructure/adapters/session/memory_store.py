from __future__ import annotations
from datetime import datetime, timezone
from typing import Tuple
from senasa_pipeline.application.ports.session_store_port import SessionStorePort

class InMemorySessionStore(SessionStorePort):
    """Simple in-memory store for development. Not persistent."""

    def __init__(self) -> None:
        self._cookies: dict[str, str] = {}
        self._expires_at: datetime | None = None
        self._is_active: bool = False

    def load(self) -> tuple[dict[str, str], datetime | None, bool]:
        return dict(self._cookies), self._expires_at, self._is_active

    def save(self, cookies: dict[str, str], expires_at: datetime) -> None:
        self._cookies = dict(cookies)
        self._expires_at = expires_at.astimezone(timezone.utc)
        self._is_active = True

    def mark_inactive(self) -> None:
        self._is_active = False
