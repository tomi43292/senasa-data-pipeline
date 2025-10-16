from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Depends

from senasa_pipeline.application.use_cases import (
    SyncSenasaDataUseCase,
    ExportSenasaDataUseCase,
    SyncRequestDTO,
    ExportRequestDTO,
)
from senasa_pipeline.infrastructure.adapters import (
    DuckDBSenasaRepository,
    ParquetStorageAdapter,
    SenasaWebScrapingAdapter,
    SimpleNotificationAdapter,
)

# Dependencias simples (en DI real usar container/wire)
repo = DuckDBSenasaRepository()
scraper = SenasaWebScrapingAdapter()
notifier = SimpleNotificationAdapter()
storage = ParquetStorageAdapter()

router = APIRouter(prefix="/v1/senasa", tags=["senasa"])

@router.post("/sync")
def sync_endpoint(body: dict[str, Any] | None = None):
    req = SyncRequestDTO(incremental=bool(body or {}).get("incremental", False))
    uc = SyncSenasaDataUseCase(scraper=scraper, validator=lambda r: True, repo=repo, notifier=notifier)  # type: ignore[arg-type]
    processed = uc.execute(req)
    return {"processed": processed}

@router.get("/records")
def list_records(limit: int = 100, offset: int = 0):
    rows = [
        {
            "nro_senasa": str(r.tambor.nro_senasa),
            "establecimiento_codigo": str(r.tambor.establecimiento_codigo),
            "peso": r.tambor.peso,
        }
        for r in repo.list(limit=limit, offset=offset)
    ]
    return {"items": rows, "count": len(rows)}

@router.post("/export")
def export_records(body: dict[str, Any]):
    req = ExportRequestDTO(format=body.get("format", "parquet"))
    uc = ExportSenasaDataUseCase(repo=repo, storage=storage)
    out = uc.execute(req, path=body.get("path", "export.parquet"))
    return {"path": out}
