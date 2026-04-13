from __future__ import annotations

import pandas as pd


class ValidadorCBAOficial:
    def __init__(self, tolerancia: float = 0.5) -> None:
        self.tolerancia = tolerancia

    def validar_reconciliacion(
        self,
        detalle: pd.DataFrame,
        consolidado: pd.DataFrame,
    ) -> pd.DataFrame:
        df_totales = detalle[detalle["CategoriaNombre"].astype(str).str.upper() == "CBA"].copy()
        if df_totales.empty:
            raise RuntimeError("No se encontró la categoría total 'CBA' en los archivos oficiales detallados.")

        comparacion = consolidado.merge(
            df_totales[["FechaID", "Zona", "CostoPerCapita"]],
            on=["FechaID", "Zona"],
            how="left",
        )
        comparacion["CostoPerCapita"] = pd.to_numeric(comparacion["CostoPerCapita"], errors="coerce")
        comparacion["CostoPerCapitaControl"] = pd.to_numeric(
            comparacion["CostoPerCapitaControl"],
            errors="coerce",
        )
        comparacion["DiferenciaAbsoluta"] = (
            comparacion["CostoPerCapita"] - comparacion["CostoPerCapitaControl"]
        ).abs()

        inconsistentes = comparacion[
            comparacion["CostoPerCapita"].isna()
            | (comparacion["DiferenciaAbsoluta"] > self.tolerancia)
        ]
        if not inconsistentes.empty:
            ejemplos = inconsistentes.head(5)[
                ["FechaID", "Zona", "CostoPerCapita", "CostoPerCapitaControl", "DiferenciaAbsoluta"]
            ].to_dict(orient="records")
            raise RuntimeError(
                "La reconciliación de la CBA oficial no coincide con el consolidado mensual. "
                f"Ejemplos: {ejemplos}"
            )
        return comparacion
