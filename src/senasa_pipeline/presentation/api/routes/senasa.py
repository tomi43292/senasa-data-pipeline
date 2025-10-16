from typing import Any
from fastapi import APIRouter
from senasa_pipeline.application.use_cases.sync_senasa_data import SyncSenasaDataUseCase
from senasa_pipeline.application.use_cases.export_senasa_data import ExportSenasaDataUseCase
from senasa_pipeline.application.dtos.sync_request_dto import SyncRequestDTO
from senasa_pipeline.application.dtos.export_request_dto import ExportRequestDTO
from senasa_pipeline.infrastructure.repositories.duckdb_repository import DuckDBSenasaRepository
from senasa_pipeline.infrastructure.adapters.scraping_adapter import SenasaWebScrapingAdapter
from senasa_pipeline.infrastructure.adapters.notification_adapter import SimpleNotificationAdapter
from senasa_pipeline.infrastructure.adapters.storage_adapter import ParquetStorageAdapter

router = APIRouter(prefix="/v1/senasa", tags=["senasa"])

_repo = DuckDBSenasaRepository()
_scraper = SenasaWebScrapingAdapter()
_notifier = SimpleNotificationAdapter()
_storage = ParquetStorageAdapter()

@router.post("/sync")
def sync_endpoint(body: dict[str, Any] | None = None):  # type: ignore[misc]
    req = SyncRequestDTO(incremental=bool(body or {}).get("incremental", False))
    uc = SyncSenasaDataUseCase(scraper=_scraper, validator=lambda r: True, repo=_repo)  # type: ignore[arg-type]
    processed = uc.execute(req)
    _notifier.notify("sync_finished", {"processed": processed})
    return {"processed": processed}

@router.get("/records")
def list_records(limit: int = 100, offset: int = 0):  # type: ignore[misc]
    rows = [
        {
            "nro_senasa": str(r.tambor.nro_senasa),
            "establecimiento_codigo": str(r.tambor.establecimiento_codigo),
            "peso": r.tambor.peso,
        }
        for r in _repo.list(limit=limit, offset=offset)
    ]
    return {"items": rows, "count": len(rows)}

@router.post("/export")
def export_records(body: dict[str, Any]):  # type: ignore[misc]
    req = ExportRequestDTO(format=body.get("format", "parquet"))
    uc = ExportSenasaDataUseCase(repo=_repo, storage=_storage)
    out = uc.execute(req, path=body.get("path", "export.parquet"))
    return {"path": out}
