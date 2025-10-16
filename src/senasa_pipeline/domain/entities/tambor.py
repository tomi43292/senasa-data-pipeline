from dataclasses import dataclass
from datetime import date
from senasa_pipeline.domain.value_objects.codigo_senasa import CodigoSenasa

@dataclass(frozen=True)
class Tambor:
    nro_senasa: CodigoSenasa
    establecimiento_codigo: CodigoSenasa
    fecha_extraccion: date
    peso: float
    tipo_miel: str
    origen: str
    productor: str
