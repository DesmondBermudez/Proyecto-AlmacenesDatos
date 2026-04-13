from __future__ import annotations

from dataclasses import dataclass


FUENTE_ARESEP = 2
FUENTE_RESPALDO = 3


@dataclass(slots=True)
class RegistroProductoCombustible:
    nombre_raw: str
    nombre_normalizado: str
    categoria: str = "Combustibles"
    subcategoria: str = "Hidrocarburos"
    unidad_medida: str = "Litro"
    fuente_id: int = FUENTE_ARESEP


@dataclass(slots=True)
class RegistroPrecioCombustible:
    fecha_raw: str
    nombre_producto_raw: str
    precio: float
    fuente_id: int = FUENTE_ARESEP
