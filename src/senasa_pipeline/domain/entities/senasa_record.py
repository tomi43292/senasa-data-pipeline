from dataclasses import dataclass

from senasa_pipeline.domain.entities.establecimiento import Establecimiento
from senasa_pipeline.domain.entities.tambor import Tambor


@dataclass(frozen=True)
class SenasaRecord:
    tambor: Tambor
    establecimiento: Establecimiento | None = None
