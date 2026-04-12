from __future__ import annotations

from pathlib import Path

import pandas as pd


class CargadorClima:
    def __init__(self, ruta_salida_csv: Path) -> None:
        self.ruta_salida_csv = ruta_salida_csv

    def guardar_csv(self, dataframe: pd.DataFrame) -> Path:
        self.ruta_salida_csv.parent.mkdir(parents=True, exist_ok=True)
        dataframe.to_csv(self.ruta_salida_csv, index=False, encoding="utf-8-sig")
        return self.ruta_salida_csv
