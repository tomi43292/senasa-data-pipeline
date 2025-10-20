from collections.abc import Sequence

from senasa_pipeline.domain.entities.senasa_record import SenasaRecord
from senasa_pipeline.domain.repositories.interfaces import ISenasaRepository
from senasa_pipeline.domain.value_objects.codigo_senasa import CodigoSenasa


class DuckDBSenasaRepository(ISenasaRepository):
    def __init__(self) -> None:
        self._data: list[SenasaRecord] = []

    def save(self, record: SenasaRecord) -> None:
        self._data.append(record)

    def get_by_nro(self, nro_senasa: CodigoSenasa) -> SenasaRecord | None:
        return next((r for r in self._data if r.tambor.nro_senasa == nro_senasa), None)

    def list(self, limit: int = 100, offset: int = 0) -> Sequence[SenasaRecord]:
        return self._data[offset : offset + limit]
