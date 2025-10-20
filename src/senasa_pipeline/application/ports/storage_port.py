from collections.abc import Sequence
from typing import Protocol

from senasa_pipeline.application.dtos.senasa_record_dto import SenasaRecordDTO


class IStoragePort(Protocol):
    def export(self, rows: Sequence[SenasaRecordDTO], fmt: str, path: str) -> str: ...
