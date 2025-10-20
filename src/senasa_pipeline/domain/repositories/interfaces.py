from collections.abc import Sequence
from typing import Protocol

from senasa_pipeline.domain.entities.establecimiento import Establecimiento
from senasa_pipeline.domain.entities.senasa_record import SenasaRecord
from senasa_pipeline.domain.value_objects.codigo_senasa import CodigoSenasa


class ISenasaRepository(Protocol):
    def save(self, record: SenasaRecord) -> None: ...
    def get_by_nro(self, nro_senasa: CodigoSenasa) -> SenasaRecord | None: ...
    def list(self, limit: int = 100, offset: int = 0) -> Sequence[SenasaRecord]: ...


class IEstablecimientoRepository(Protocol):
    def upsert(self, est: Establecimiento) -> None: ...
    def get(self, codigo: CodigoSenasa) -> Establecimiento | None: ...
