from __future__ import annotations

from dataclasses import dataclass
from datetime import date


FUENTE_HACIENDA = 1
FUENTE_RESPALDO = 3


@dataclass(slots=True)
class RegistroTipoCambio:
    fecha: date
    compra: float
    venta: float
    moneda_base_id: int = 1
    moneda_referencia_id: int = 2
    fuente_id: int = FUENTE_HACIENDA
