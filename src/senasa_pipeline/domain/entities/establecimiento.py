from dataclasses import dataclass

from senasa_pipeline.domain.value_objects.codigo_senasa import CodigoSenasa
from senasa_pipeline.domain.value_objects.cuit import CUIT
from senasa_pipeline.domain.value_objects.fecha_vencimiento import FechaVencimiento


@dataclass(frozen=True)
class Establecimiento:
    codigo_senasa: CodigoSenasa
    nombre: str
    direccion: str
    localidad: str
    provincia: str
    cuit: CUIT
    fecha_vencimiento: FechaVencimiento
