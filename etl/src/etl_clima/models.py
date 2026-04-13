from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


FUENTE_NASA = 4


@dataclass(slots=True)
class ZonaClimatica:
    nombre: str
    latitud: float
    longitud: float


@dataclass(slots=True)
class RegistroClimaMensual:
    zona: str
    latitud: float
    longitud: float
    anio: int
    mes: int
    temp_max: float
    temp_min: float
    precipitacion: float
    humedad: float
    radiacion_solar: float


@dataclass(slots=True)
class ConfiguracionExtraccionClima:
    start_year: str = "2011"
    end_year: str = field(default_factory=lambda: str(date.today().year))
    base_url: str = "https://power.larc.nasa.gov/api/temporal/monthly/point"

    def rango_anios(self) -> tuple[int, int]:
        inicio = int(self.start_year)
        fin = int(self.end_year)
        if inicio > fin:
            raise ValueError(
                f"Rango de clima invalido: start_year={self.start_year} es mayor que end_year={self.end_year}."
            )
        return inicio, fin
