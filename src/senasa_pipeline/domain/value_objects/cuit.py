class CUIT(str):
    """Value Object para CUIT (11 dígitos)."""
    def __new__(cls, value: str) -> "CUIT":
        assert value.isdigit() and len(value) == 11, "CUIT inválido"
        return str.__new__(cls, value)
