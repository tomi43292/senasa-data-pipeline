from __future__ import annotations
from fastapi import APIRouter
from senasa_pipeline.application.use_cases.ensure_senasa_session import EnsureSenasaSessionUseCase, SystemClock
from senasa_pipeline.infrastructure.adapters.http.httpx_client import HttpxClient
from senasa_pipeline.infrastructure.adapters.afip.portal_cf_provider import PortalCFProvider
from senasa_pipeline.infrastructure.adapters.senasa.login_consumer import SenasaLoginConsumer
from senasa_pipeline.infrastructure.adapters.session.memory_store import InMemorySessionStore
from senasa_pipeline.config import settings

router = APIRouter(prefix="/v1/auth", tags=["auth"]) 

@router.post("/ensure_session")
def ensure_session() -> dict[str, str]:  # type: ignore[misc]
    http = HttpxClient(timeout=settings.http_timeout)
    store = InMemorySessionStore()
    provider = PortalCFProvider(http=http, cuit=settings.afip_cuit)
    consumer = SenasaLoginConsumer(http=http)
    uc = EnsureSenasaSessionUseCase(store=store, provider=provider, consumer=consumer, clock=SystemClock(), ttl_hours=settings.session_ttl_hours)
    result = uc.execute()
    return {"status": result.status, "expires_at": result.expires_at.isoformat() if result.expires_at else None, "message": result.message}
