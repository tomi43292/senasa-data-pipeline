from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol


class SessionData(Mapping[str, Any]):
    """Typed view over session payload if needed later."""

    # For now inherit Mapping for flexibility; concrete implementations can subclass dict


class SessionStorePort(Protocol):
    """Abstract persistence for SENASA session cookies and metadata."""

    def load(self) -> tuple[dict[str, str], datetime | None, bool]:
        """
        Returns:
            cookies: mapping cookie_name -> value
            expires_at: when the session should be considered expired (UTC) or None
            is_active: flag indicating previously valid session
        """
        ...

    def save(self, cookies: dict[str, str], expires_at: datetime) -> None:
        """Persist cookies and expiry, marking session active."""
        ...

    def mark_inactive(self) -> None:
        """Mark the stored session as inactive (e.g., after failed probe)."""
        ...
