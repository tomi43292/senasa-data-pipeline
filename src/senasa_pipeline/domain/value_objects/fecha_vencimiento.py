from datetime import date


class FechaVencimiento(date):
    @classmethod
    def from_date(cls, d: date) -> "FechaVencimiento":
        return cls(d.year, d.month, d.day)
