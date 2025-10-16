from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from senasa_pipeline.application.use_cases import (
    INotificationPort,
    ISenasaDataPort,
    IStoragePort,
    SenasaRecordDTO,
)
from senasa_pipeline.domain.model import (
    CUIT,
    CodigoSenasa,
    EstablecimientoSenasa,
    FechaVencimiento,
    ISenasaRepository,
    ISenasaScrapingService,
    SenasaRecord,
    TamborSenasa,
)


# =========================
# Repositories
# =========================
class DuckDBSenasaRepository(ISenasaRepository):
    def __init__(self) -> None:
        self._data: list[SenasaRecord] = []  # placeholder en memoria

    def save(self, record: SenasaRecord) -> None:
        self._data.append(record)

    def get_by_nro(self, nro_senasa: CodigoSenasa) -> SenasaRecord | None:
        return next((r for r in self._data if r.tambor.nro_senasa == nro_senasa), None)

    def list(self, limit: int = 100, offset: int = 0) -> Sequence[SenasaRecord]:
        return self._data[offset : offset + limit]

class PostgreSQLSenasaRepository(ISenasaRepository):
    def save(self, record: SenasaRecord) -> None: ...
    def get_by_nro(self, nro_senasa: CodigoSenasa) -> SenasaRecord | None: ...
    def list(self, limit: int = 100, offset: int = 0) -> Sequence[SenasaRecord]:
        return []

# =========================
# External Services (Scraping/APIs)
# =========================
class SenasaWebScrapingAdapter(ISenasaScrapingService):
    def fetch_latest(self, incremental: bool = False) -> Sequence[SenasaRecord]:
        # Placeholder: devolver 0..N registros simulados
        return []

class SenasaAPIAdapter(ISenasaScrapingService):
    def fetch_latest(self, incremental: bool = False) -> Sequence[SenasaRecord]:
        return []

# =========================
# Storage Adapters
# =========================
class ParquetStorageAdapter(IStoragePort):
    def export(self, rows: Sequence[SenasaRecordDTO], fmt: str, path: str) -> str:
        out = Path(path)
        out.write_text("parquet export placeholder")
        return str(out)

class ExcelExportAdapter(IStoragePort):
    def export(self, rows: Sequence[SenasaRecordDTO], fmt: str, path: str) -> str:
        out = Path(path)
        out.write_text("xlsx export placeholder")
        return str(out)

# =========================
# Notification Adapter
# =========================
class SimpleNotificationAdapter(INotificationPort):
    def notify(self, event: str, payload: dict[str, Any]) -> None:
        # En real: Slack/Email/Telegram/Webhook
        print(f"[{event}] {payload}")
