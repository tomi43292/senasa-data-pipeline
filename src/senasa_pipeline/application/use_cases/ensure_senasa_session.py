from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from senasa_pipeline.application.ports.session_store_port import SessionStorePort
from senasa_pipeline.application.ports.auth_provider_port import AuthProviderPort
from senasa_pipeline.application.ports.senasa_login_port import SenasaLoginPort

class Clock(Protocol):
    def now(self) -> datetime: ...

class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

@dataclass(frozen=True)
class EnsureSessionResult:
    status: str  # "ALREADY_ACTIVE" | "REFRESHED" | "ERROR"
    expires_at: datetime | None
    message: str

class EnsureSenasaSessionUseCase:
    """Orchestrates AFIP→SENASA login, preferring cached session when valid."""

    def __init__(
        self,
        store: SessionStorePort,
        provider: AuthProviderPort,
        consumer: SenasaLoginPort,
        *,
        ttl_hours: int = 12,
        clock: Clock | None = None,
    ) -> None:
        self.store = store
        self.provider = provider
        self.consumer = consumer
        self.ttl = timedelta(hours=ttl_hours)
        self.clock = clock or SystemClock()

    def execute(self) -> EnsureSessionResult:
        cookies, expires_at, is_active = self.store.load()
        # If we have cookies and not expired, attempt validation probe
        now = self.clock.now()
        if cookies and expires_at and expires_at > now and is_active:
            try:
                if self.consumer.validate_session():
                    return EnsureSessionResult("ALREADY_ACTIVE", expires_at, "Valid session from store")
            except Exception:
                # ignore and re-login
                pass
        # Fresh login via AFIP token/sign path
        try:
            token, sign = self.provider.get_token_sign()
            self.consumer.login_with_token_sign(token, sign)
            new_exp = now + self.ttl
            # Persist cookies via consumer/store contract: the store should be updated by caller after dumping cookies
            # Here we assume consumer updated HTTP client's cookies; store persists them
            # For clarity, consumer.validate_session() after login
            if not self.consumer.validate_session():
                self.store.mark_inactive()
                return EnsureSessionResult("ERROR", None, "Post-login validation failed")
            # Ask external to dump cookies? We keep persistence at adapter layer; here just set expiry
            self.store.save({}, new_exp)  # Adapters should override to include real cookies
            return EnsureSessionResult("REFRESHED", new_exp, "Session refreshed via AFIP token/sign")
        except Exception as e:
            self.store.mark_inactive()
            return EnsureSessionResult("ERROR", None, f"Login failed: {e}")
