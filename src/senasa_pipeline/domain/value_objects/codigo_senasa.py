class CodigoSenasa(str):
    def __new__(cls, value: str) -> "CodigoSenasa":
        assert len(value) >= 3, "Código SENASA inválido"
        return str.__new__(cls, value)
