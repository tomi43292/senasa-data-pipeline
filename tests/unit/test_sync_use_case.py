# Pytest básico para casos de uso
from senasa_pipeline.application.use_cases.sync_senasa_data import SyncSenasaDataUseCase
from senasa_pipeline.application.dtos.sync_request_dto import SyncRequestDTO
from senasa_pipeline.domain.entities.tambor import Tambor
from senasa_pipeline.domain.entities.establecimiento import Establecimiento
from senasa_pipeline.domain.entities.senasa_record import SenasaRecord
from senasa_pipeline.domain.value_objects.codigo_senasa import CodigoSenasa
from senasa_pipeline.domain.value_objects.cuit import CUIT
from senasa_pipeline.domain.value_objects.fecha_vencimiento import FechaVencimiento
from senasa_pipeline.infrastructure.repositories.duckdb_repository import DuckDBSenasaRepository

class FakeScraper:
    def fetch_latest(self, incremental: bool = False):
        t = Tambor(CodigoSenasa("ABC123"), CodigoSenasa("EST001"), __import__("datetime").date.today(), 300.0, "flores", "AR", "Juan")
        e = Establecimiento(CodigoSenasa("EST001"), "Est 1", "Dir", "Loc", "Prov", CUIT("20301234567"), FechaVencimiento.from_date(__import__("datetime").date.today()))
        return [SenasaRecord(tambor=t, establecimiento=e)]

class AlwaysValid:
    def validate(self, record):
        return True

def test_sync_use_case_processes_records():
    repo = DuckDBSenasaRepository()
    uc = SyncSenasaDataUseCase(scraper=FakeScraper(), validator=AlwaysValid(), repo=repo)
    processed = uc.execute(SyncRequestDTO(incremental=False))
    assert processed == 1
    assert repo.get_by_nro(CodigoSenasa("ABC123")) is not None
