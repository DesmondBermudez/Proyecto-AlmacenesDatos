from __future__ import annotations

from dataclasses import dataclass


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
    start_year: str = "2019"
    end_year: str = "2024"
    base_url: str = "https://power.larc.nasa.gov/api/temporal/monthly/point"
