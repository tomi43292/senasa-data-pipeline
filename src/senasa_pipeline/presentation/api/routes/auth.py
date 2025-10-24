from __future__ import annotations
from fastapi import APIRouter
import os
from senasa_pipeline.application.use_cases.ensure_senasa_session import EnsureSenasaSessionUseCase, SystemClock
from senasa_pipeline.infrastructure.adapters.http.httpx_client import HttpxClient
from senasa_pipeline.infrastructure.adapters.afip.unified_provider import UnifiedAfipProvider
from senasa_pipeline.infrastructure.adapters.senasa.login_consumer import SenasaLoginConsumer
from senasa_pipeline.infrastructure.adapters.session.sqlite_store import SQLiteSessionStore
from senasa_pipeline.config import settings

router = APIRouter(prefix="/v1/auth", tags=["auth"]) 

@router.post("/ensure_session")
def ensure_session() -> dict[str, str | None]:  # type: ignore[misc]
    # Único HttpxClient compartido para mantener sesión unificada AFIP+SENASA
    http = HttpxClient(timeout=settings.http_timeout)
    
    # Adaptadores con sesión HTTP compartida
    provider = UnifiedAfipProvider(
        http=http, 
        cuit=settings.afip_cuit, 
        password=os.getenv("AFIP_PASSWORD", "")
    )
    consumer = SenasaLoginConsumer(http=http)
    
    # Store y use case
    store = SQLiteSessionStore(db_path=".senasa_auth.sqlite")
    use_case = EnsureSenasaSessionUseCase(
        store=store, 
        provider=provider, 
        consumer=consumer, 
        clock=SystemClock(), 
        ttl_hours=settings.session_ttl_hours
    )
    
    # Ejecutar caso de uso
    result = use_case.execute()
    
    # Persistir si exitoso
    if result.status in ("REFRESHED", "ALREADY_ACTIVE"):
        store.save(consumer.cookies or http.dump_cookies(), result.expires_at or SystemClock().now())
    
    return {
        "status": result.status, 
        "expires_at": result.expires_at.isoformat() if result.expires_at else None, 
        "message": result.message
    }
