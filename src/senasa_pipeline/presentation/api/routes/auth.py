from __future__ import annotations
from fastapi import APIRouter
from senasa_pipeline.application.use_cases.ensure_senasa_session import EnsureSenasaSessionUseCase, SystemClock
from senasa_pipeline.infrastructure.adapters.http.httpx_client import HttpxClient
from senasa_pipeline.infrastructure.adapters.afip.portal_cf_provider import PortalCFProvider
from senasa_pipeline.infrastructure.adapters.afip.jsf_provider import JSFProvider
from senasa_pipeline.infrastructure.adapters.senasa.login_consumer import SenasaLoginConsumer
from senasa_pipeline.infrastructure.adapters.session.sqlite_store import SQLiteSessionStore
from senasa_pipeline.config import settings

router = APIRouter(prefix="/v1/auth", tags=["auth"]) 

@router.post("/ensure_session")
def ensure_session() -> dict[str, str]:  # type: ignore[misc]
    http = HttpxClient(timeout=settings.http_timeout)
    store = SQLiteSessionStore(db_path=".senasa_auth.sqlite")
    consumer = SenasaLoginConsumer(http=http)

    # Intento 1: Portal CF
    try:
        provider = PortalCFProvider(http=http, cuit=settings.afip_cuit)
        uc = EnsureSenasaSessionUseCase(store=store, provider=provider, consumer=consumer, clock=SystemClock(), ttl_hours=settings.session_ttl_hours)
        result = uc.execute()
        if result.status in ("REFRESHED", "ALREADY_ACTIVE"):
            store.save(consumer.cookies or http.dump_cookies(), result.expires_at or SystemClock().now())
            return {"status": result.status, "expires_at": result.expires_at.isoformat() if result.expires_at else None, "message": result.message}
    except Exception as e:
        # Continuar a fallback JSF
        pass

    # Intento 2: JSF clásico (requiere password)
    provider_jsf = JSFProvider(http=http, cuit=settings.afip_cuit, password=os.getenv("AFIP_PASSWORD", ""))
    uc2 = EnsureSenasaSessionUseCase(store=store, provider=provider_jsf, consumer=consumer, clock=SystemClock(), ttl_hours=settings.session_ttl_hours)
    result2 = uc2.execute()
    if result2.status in ("REFRESHED", "ALREADY_ACTIVE"):
        store.save(consumer.cookies or http.dump_cookies(), result2.expires_at or SystemClock().now())
    return {"status": result2.status, "expires_at": result2.expires_at.isoformat() if result2.expires_at else None, "message": result2.message}
