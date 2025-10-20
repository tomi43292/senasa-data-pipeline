from dataclasses import dataclass

from senasa_pipeline.domain.entities.senasa_record import SenasaRecord


@dataclass(frozen=True)
class SenasaRecordDTO:
    nro_senasa: str
    establecimiento_codigo: str
    peso: float
    tipo_miel: str
    origen: str
    productor: str

    @classmethod
    def from_domain(cls, rec: SenasaRecord) -> "SenasaRecordDTO":
        t = rec.tambor
        return cls(
            nro_senasa=str(t.nro_senasa),
            establecimiento_codigo=str(t.establecimiento_codigo),
            peso=t.peso,
            tipo_miel=t.tipo_miel,
            origen=t.origen,
            productor=t.productor,
        )
