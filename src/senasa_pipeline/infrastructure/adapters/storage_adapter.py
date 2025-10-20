from collections.abc import Sequence
from pathlib import Path

from senasa_pipeline.application.dtos.senasa_record_dto import SenasaRecordDTO


class ParquetStorageAdapter:
    def export(self, rows: Sequence[SenasaRecordDTO], fmt: str, path: str) -> str:
        out = Path(path)
        out.write_text("parquet export placeholder")
        return str(out)


class ExcelExportAdapter:
    def export(self, rows: Sequence[SenasaRecordDTO], fmt: str, path: str) -> str:
        out = Path(path)
        out.write_text("xlsx export placeholder")
        return str(out)
