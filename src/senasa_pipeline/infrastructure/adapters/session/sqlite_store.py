from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from senasa_pipeline.application.ports.session_store_port import SessionStorePort

SCHEMA = """
CREATE TABLE IF NOT EXISTS senasa_session (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  cookies TEXT NOT NULL,
  expires_at TEXT,
  is_active INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO senasa_session (id, cookies, expires_at, is_active) VALUES (1, '{}', NULL, 0);
"""


class SQLiteSessionStore(SessionStorePort):
    """SQLite-backed session store. Persists cookies/expiry across restarts.

    File path configurable; creates schema on first use.
    """

    def __init__(self, db_path: str = ".senasa_auth.sqlite") -> None:
        self._path = Path(db_path)
        self._conn = sqlite3.connect(self._path)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def load(self) -> tuple[dict[str, str], datetime | None, bool]:
        cur = self._conn.execute(
            "SELECT cookies, expires_at, is_active FROM senasa_session WHERE id=1"
        )
        row = cur.fetchone()
        if not row:
            return {}, None, False
        import json

        cookies_str, expires_iso, active_int = row
        cookies = json.loads(cookies_str or "{}")
        expires = None
        if expires_iso:
            try:
                expires = datetime.fromisoformat(expires_iso)
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=UTC)
            except Exception:
                expires = None
        return cookies, expires, bool(active_int)

    def save(self, cookies: dict[str, str], expires_at: datetime) -> None:
        import json

        expires_iso = expires_at.astimezone(UTC).isoformat()
        self._conn.execute(
            "UPDATE senasa_session SET cookies=?, expires_at=?, is_active=1 WHERE id=1",
            (json.dumps(cookies), expires_iso),
        )
        self._conn.commit()

    def mark_inactive(self) -> None:
        self._conn.execute("UPDATE senasa_session SET is_active=0 WHERE id=1")
        self._conn.commit()
