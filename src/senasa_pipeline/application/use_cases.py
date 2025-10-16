from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Any, Sequence
from senasa_pipeline.domain.model import (
    SenasaRecord,
    ISenasaRepository,
    IDataValidationService,
    ISenasaScrapingService,
)

# =========================
# DTOs
# =========================
@dataclass(frozen=True)
class SenasaRecordDTO:
    nro_senasa: str
    establecimiento_codigo: str
    peso: float
    tipo_miel: str
    origen: str
    productor: str

    @classmethod
    def from_domain(cls, rec: SenasaRecord) -> "SenasaRecordDTO":
        t = rec.tambor
        return cls(
            nro_senasa=str(t.nro_senasa),
            establecimiento_codigo=str(t.establecimiento_codigo),
            peso=t.peso,
            tipo_miel=t.tipo_miel,
            origen=t.origen,
            productor=t.productor,
        )

@dataclass(frozen=True)
class SyncRequestDTO:
    incremental: bool = False

@dataclass(frozen=True)
class ExportRequestDTO:
    format: str = "parquet"  # csv|xlsx|parquet

# =========================
# Ports (Application-facing)
# =========================
class ISenasaDataPort(Protocol):
    def save_many(self, records: Sequence[SenasaRecordDTO]) -> int: ...
    def query(self, filtros: dict[str, Any]) -> Sequence[SenasaRecordDTO]: ...

class INotificationPort(Protocol):
    def notify(self, event: str, payload: dict[str, Any]) -> None: ...

class IStoragePort(Protocol):
    def export(self, rows: Sequence[SenasaRecordDTO], fmt: str, path: str) -> str: ...

# =========================
# Use Cases
# =========================
class SyncSenasaDataUseCase:
    def __init__(
        self,
        scraper: ISenasaScrapingService,
        validator: IDataValidationService,
        repo: ISenasaRepository,
        notifier: INotificationPort | None = None,
    ) -> None:
        self.scraper = scraper
        self.validator = validator
        self.repo = repo
        self.notifier = notifier

    def execute(self, req: SyncRequestDTO) -> int:
        if self.notifier:
            self.notifier.notify("sync_started", {"incremental": req.incremental})
        count = 0
        for rec in self.scraper.fetch_latest(incremental=req.incremental):
            if self.validator.validate(rec):
                self.repo.save(rec)
                count += 1
        if self.notifier:
            self.notifier.notify("sync_finished", {"processed": count})
        return count

class ExportSenasaDataUseCase:
    def __init__(self, repo: ISenasaRepository, storage: IStoragePort) -> None:
        self.repo = repo
        self.storage = storage

    def execute(self, req: ExportRequestDTO, path: str) -> str:
        rows = [SenasaRecordDTO.from_domain(r) for r in self.repo.list(limit=10000, offset=0)]
        return self.storage.export(rows, req.format, path)

class ValidateSenasaRecordUseCase:
    def __init__(self, validator: IDataValidationService) -> None:
        self.validator = validator

    def execute(self, record: SenasaRecord) -> bool:
        return self.validator.validate(record)
