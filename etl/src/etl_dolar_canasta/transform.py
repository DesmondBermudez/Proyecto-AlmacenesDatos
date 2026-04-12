from __future__ import annotations

from pathlib import Path

import pandas as pd

from etl_dolar_canasta.combustibles import clasificar_producto_combustible
from etl_dolar_canasta.models import (
    FUENTE_ARESEP,
    RegistroPrecioCombustible,
    RegistroProductoCombustible,
)


class TransformadorCombustible:
    def transformar(
        self, registros: list[dict]
    ) -> tuple[list[RegistroProductoCombustible], list[RegistroPrecioCombustible]]:
        productos: list[RegistroProductoCombustible] = []
        precios: list[RegistroPrecioCombustible] = []
        vistos: set[str] = set()

        for reg in registros:
            nombre_raw = (reg.get("producto") or "").strip()
            if not nombre_raw:
                continue

            clasificacion = clasificar_producto_combustible(nombre_raw)
            if clasificacion is None:
                continue

            fuente_id = int(reg.get("fuente_id") or FUENTE_ARESEP)
            nombre_canonico = clasificacion["nombre_canonico"]

            if reg.get("precioFinal") is None or not str(reg.get("fechaPublicacion") or "").strip():
                continue

            if nombre_canonico not in vistos:
                productos.append(
                    RegistroProductoCombustible(
                        nombre_raw=nombre_canonico,
                        nombre_normalizado=nombre_canonico,
                        categoria=clasificacion["categoria"],
                        subcategoria=clasificacion["subcategoria"],
                        unidad_medida=clasificacion["unidad_medida"],
                        fuente_id=fuente_id,
                    )
                )
                vistos.add(nombre_canonico)

            precios.append(
                RegistroPrecioCombustible(
                    fecha_raw=str(reg.get("fechaPublicacion") or ""),
                    nombre_producto_raw=nombre_canonico,
                    precio=float(reg["precioFinal"]),
                    fuente_id=fuente_id,
                )
            )

        return productos, precios


class TransformadorCanasta:
    def leer_y_transformar(self, ruta_csv: Path) -> pd.DataFrame:
        df = pd.read_csv(ruta_csv)
        for columna in ["Provincia", "Canton", "Distrito", "NombreProducto"]:
            if columna in df.columns:
                df[columna] = df[columna].astype(str).str.upper().str.strip()
        df["PrecioColones"] = pd.to_numeric(df["PrecioColones"], errors="coerce")
        df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.strftime("%Y-%m-%d")
        return df.dropna(subset=["PrecioColones"])
