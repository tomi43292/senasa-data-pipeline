from collections.abc import Sequence

from senasa_pipeline.domain.entities.senasa_record import SenasaRecord


class SenasaWebScrapingAdapter:
    def fetch_latest(self, incremental: bool = False) -> Sequence[SenasaRecord]:
        return []
