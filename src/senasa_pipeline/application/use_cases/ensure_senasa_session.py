from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
import time

from senasa_pipeline.application.ports.auth_provider_port import AuthProviderPort
from senasa_pipeline.application.ports.senasa_login_port import SenasaLoginPort
from senasa_pipeline.application.ports.session_store_port import SessionStorePort


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


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
        session_exists = cookies and expires_at and expires_at > now and is_active
        if session_exists:
            try:
                if self.consumer.validate_session():
                    return EnsureSessionResult(
                        "ALREADY_ACTIVE", expires_at, "Valid session from store"
                    )
            except Exception:
                # ignore and re-login
                pass
        # Fresh login via AFIP token/sign path
        try:
            print("Fresh login via AFIP token/sign path")
            token, sign = self.provider.get_token_sign()
            print(f"Token: {token}, Sign: {sign}")
            self.consumer.login_with_token_sign(token, sign)
            new_exp = now + self.ttl
            
            # CRITICAL: Post-login validation with retry for timing issues
            # The follow-up needs time to complete before validation works
            validation_success = self._validate_with_retry(max_retries=3, delay=1.0)
            
            if not validation_success:
                self.store.mark_inactive()
                return EnsureSessionResult("ERROR", None, "Post-login validation failed after retries")
            
            # Save successful session
            self.store.save(
                self.consumer.cookies, new_exp
            )
            return EnsureSessionResult(
                "REFRESHED", new_exp, "Session refreshed via AFIP token/sign"
            )
        except Exception as e:
            self.store.mark_inactive()
            return EnsureSessionResult("ERROR", None, f"Login failed: {e}")
    
    def _validate_with_retry(self, max_retries: int = 3, delay: float = 1.0) -> bool:
        """Retry validation to handle timing issues after login follow-up."""
        for attempt in range(max_retries):
            try:
                if self.consumer.validate_session():
                    return True
                    
                if attempt < max_retries - 1:  # Don't sleep after last attempt
                    print(f"[EnsureSenasaSessionUseCase] Validation attempt {attempt + 1} failed, retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= 1.5  # Exponential backoff
                    
            except Exception as e:
                print(f"[EnsureSenasaSessionUseCase] Validation attempt {attempt + 1} exception: {e}")
                if attempt < max_retries - 1:
                    time.sleep(delay)
                    delay *= 1.5
        
        return False
