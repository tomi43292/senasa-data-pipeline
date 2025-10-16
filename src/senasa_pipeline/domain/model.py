from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable, Sequence

# =========================
# Value Objects
# =========================
class CUIT(str):
    """Value Object para CUIT (11 dígitos)."""
    def __new__(cls, value: str) -> "CUIT":
        assert value.isdigit() and len(value) == 11, "CUIT inválido"
        return str.__new__(cls, value)

class CodigoSenasa(str):
    """Value Object para código SENASA (formato flexible, validación mínima)."""
    def __new__(cls, value: str) -> "CodigoSenasa":
        assert len(value) >= 3, "Código SENASA inválido"
        return str.__new__(cls, value)

class FechaVencimiento(date):
    """Value Object para fecha de vencimiento."""
    @classmethod
    def from_date(cls, d: date) -> "FechaVencimiento":
        return cls(d.year, d.month, d.day)

# =========================
# Entities
# =========================
@dataclass(frozen=True)
class EstablecimientoSenasa:
    codigo_senasa: CodigoSenasa
    nombre: str
    direccion: str
    localidad: str
    provincia: str
    cuit: CUIT
    fecha_vencimiento: FechaVencimiento

@dataclass(frozen=True)
class TamborSenasa:
    nro_senasa: CodigoSenasa
    establecimiento_codigo: CodigoSenasa
    fecha_extraccion: date
    peso: float
    tipo_miel: str
    origen: str
    productor: str

@dataclass(frozen=True)
class SenasaRecord:
    tambor: TamborSenasa
    establecimiento: EstablecimientoSenasa | None = None

# =========================
# Repository Interfaces
# =========================
@runtime_checkable
class ISenasaRepository(Protocol):
    def save(self, record: SenasaRecord) -> None: ...
    def get_by_nro(self, nro_senasa: CodigoSenasa) -> SenasaRecord | None: ...
    def list(self, limit: int = 100, offset: int = 0) -> Sequence[SenasaRecord]: ...

@runtime_checkable
class IEstablecimientoRepository(Protocol):
    def upsert(self, est: EstablecimientoSenasa) -> None: ...
    def get(self, codigo: CodigoSenasa) -> EstablecimientoSenasa | None: ...

# =========================
# Service Interfaces
# =========================
@runtime_checkable
class ISenasaScrapingService(Protocol):
    def fetch_latest(self, incremental: bool = False) -> Sequence[SenasaRecord]: ...

@runtime_checkable
class IDataValidationService(Protocol):
    def validate(self, record: SenasaRecord) -> bool: ...
