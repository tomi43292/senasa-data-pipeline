from __future__ import annotations
from fastapi import APIRouter
from senasa_pipeline.application.use_cases.ensure_senasa_session import EnsureSenasaSessionUseCase, SystemClock
from senasa_pipeline.infrastructure.adapters.http.httpx_client import HttpxClient
from senasa_pipeline.infrastructure.adapters.afip.portal_cf_provider import PortalCFProvider
from senasa_pipeline.infrastructure.adapters.senasa.login_consumer import SenasaLoginConsumer
from senasa_pipeline.infrastructure.adapters.session.memory_store import InMemorySessionStore

router = APIRouter(prefix="/v1/auth", tags=["auth"]) 

@router.post("/ensure_session")
def ensure_session() -> dict[str, str]:  # type: ignore[misc]
    http = HttpxClient()
    store = InMemorySessionStore()
    provider = PortalCFProvider(http=http, cuit="CUIT_CONFIGURAR")  # TODO: leer de settings/ENV
    consumer = SenasaLoginConsumer(http=http)
    uc = EnsureSenasaSessionUseCase(store=store, provider=provider, consumer=consumer, clock=SystemClock())
    result = uc.execute()
    return {"status": result.status, "expires_at": result.expires_at.isoformat() if result.expires_at else None, "message": result.message}
