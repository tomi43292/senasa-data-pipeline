from senasa_pipeline.application.dtos.export_request_dto import ExportRequestDTO
from senasa_pipeline.application.dtos.senasa_record_dto import SenasaRecordDTO
from senasa_pipeline.application.ports.storage_port import IStoragePort
from senasa_pipeline.domain.repositories.interfaces import ISenasaRepository


class ExportSenasaDataUseCase:
    def __init__(self, repo: ISenasaRepository, storage: IStoragePort):
        self.repo = repo
        self.storage = storage

    def execute(self, req: ExportRequestDTO, path: str) -> str:
        rows = [SenasaRecordDTO.from_domain(r) for r in self.repo.list(limit=10000, offset=0)]
        return self.storage.export(rows, req.format, path)
