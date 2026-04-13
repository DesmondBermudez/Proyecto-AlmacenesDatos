from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


FUENTE_INEC = 5
PRODUCT_FILE_PATTERNS = (
    "CBANacional_*XMESyProducto.xlsx",
    "CBAUrbano_*XMESyProducto.xlsx",
    "CBARural_*XMESyProducto.xlsx",
)
CONTROL_FILE_PATTERN = "CBA_*XMES.xlsx"
ZONE_LABELS = {
    "CBANacional": "Nacional",
    "CBAUrbano": "Urbano",
    "CBARural": "Rural",
}
MONTHS_ES = {
    1: "ene",
    2: "feb",
    3: "mar",
    4: "abr",
    5: "may",
    6: "jun",
    7: "jul",
    8: "ago",
    9: "set",
    10: "oct",
    11: "nov",
    12: "dic",
}
MONTHS_ES_FULL = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


@dataclass(slots=True)
class ResultadoExtraccionCBA:
    detalle: pd.DataFrame
    consolidado: pd.DataFrame
