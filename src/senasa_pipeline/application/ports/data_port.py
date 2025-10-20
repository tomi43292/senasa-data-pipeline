from collections.abc import Sequence
from typing import Any, Protocol

from senasa_pipeline.application.dtos.senasa_record_dto import SenasaRecordDTO


class ISenasaDataPort(Protocol):
    def save_many(self, records: Sequence[SenasaRecordDTO]) -> int: ...
    def query(self, filtros: dict[str, Any]) -> Sequence[SenasaRecordDTO]: ...
