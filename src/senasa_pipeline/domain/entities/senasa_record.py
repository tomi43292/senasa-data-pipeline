from dataclasses import dataclass
from senasa_pipeline.domain.entities.tambor import Tambor
from senasa_pipeline.domain.entities.establecimiento import Establecimiento

@dataclass(frozen=True)
class SenasaRecord:
    tambor: Tambor
    establecimiento: Establecimiento | None = None
