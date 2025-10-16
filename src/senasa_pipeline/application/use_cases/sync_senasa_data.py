from senasa_pipeline.application.dtos.sync_request_dto import SyncRequestDTO
from senasa_pipeline.domain.repositories.interfaces import (
    ISenasaRepository,
)
from senasa_pipeline.domain.model import ISenasaScrapingService, IDataValidationService
# adjust imports: recreate services protocol here to avoid circulars
from typing import Protocol
from senasa_pipeline.domain.entities.senasa_record import SenasaRecord

class ISenasaScrapingService(Protocol):
    def fetch_latest(self, incremental: bool = False) -> list[SenasaRecord]: ...

class IDataValidationService(Protocol):
    def validate(self, record: SenasaRecord) -> bool: ...

class SyncSenasaDataUseCase:
    def __init__(self, scraper: ISenasaScrapingService, validator: IDataValidationService, repo: ISenasaRepository):
        self.scraper = scraper
        self.validator = validator
        self.repo = repo

    def execute(self, req: SyncRequestDTO) -> int:
        count = 0
        for rec in self.scraper.fetch_latest(incremental=req.incremental):
            if self.validator.validate(rec):
                self.repo.save(rec)
                count += 1
        return count
