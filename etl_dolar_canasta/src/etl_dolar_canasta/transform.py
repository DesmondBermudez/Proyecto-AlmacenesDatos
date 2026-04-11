from __future__ import annotations

from pathlib import Path

import pandas as pd

from etl_dolar_canasta.models import (
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
            nombre_upper = nombre_raw.upper()
            nombre_normalizado = None
            if "RON 95" in nombre_upper:
                nombre_normalizado = "Gasolina RON 95"
            elif "RON 91" in nombre_upper:
                nombre_normalizado = "Gasolina RON 91"
            elif "DIESEL" in nombre_upper or "DIÉSEL" in nombre_upper:
                nombre_normalizado = "Diesel"
            if not nombre_normalizado:
                continue
            if nombre_raw not in vistos:
                productos.append(
                    RegistroProductoCombustible(
                        nombre_raw=nombre_raw,
                        nombre_normalizado=nombre_normalizado,
                    )
                )
                vistos.add(nombre_raw)
            if reg.get("precioFinal") is not None:
                precios.append(
                    RegistroPrecioCombustible(
                        fecha_raw=str(reg.get("fechaPublicacion") or ""),
                        nombre_producto_raw=nombre_raw,
                        precio=float(reg["precioFinal"]),
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
