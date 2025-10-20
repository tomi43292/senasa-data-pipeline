from dataclasses import dataclass


@dataclass(frozen=True)
class ExportRequestDTO:
    format: str = "parquet"
