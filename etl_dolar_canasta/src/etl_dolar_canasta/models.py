from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(slots=True)
class RegistroTipoCambio:
    fecha: date
    compra: float
    venta: float
    moneda_base_id: int = 1
    moneda_referencia_id: int = 2
    fuente_id: int = 1


@dataclass(slots=True)
class RegistroProductoCombustible:
    nombre_raw: str
    nombre_normalizado: str
    categoria: str = "Combustibles"
    subcategoria: str = "Hidrocarburos"
    unidad_medida: str = "Litro"
    fuente_id: int = 2


@dataclass(slots=True)
class RegistroPrecioCombustible:
    fecha_raw: str
    nombre_producto_raw: str
    precio: float
    fuente_id: int = 3
