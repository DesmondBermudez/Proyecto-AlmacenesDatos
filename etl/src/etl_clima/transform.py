from __future__ import annotations

import pandas as pd


class TransformadorClima:
    COLUMNAS_SALIDA = [
        "zona",
        "latitud",
        "longitud",
        "anio",
        "mes",
        "temp_max",
        "temp_min",
        "precipitacion",
        "humedad",
        "radiacion_solar",
    ]

    def transformar(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        df = dataframe.rename(
            columns={
                "Zona": "zona",
                "Latitud": "latitud",
                "Longitud": "longitud",
                "Año": "anio",
                "Anio": "anio",
                "Mes": "mes",
                "Temp_Max": "temp_max",
                "Temp_Min": "temp_min",
                "Precipitacion": "precipitacion",
                "Humedad": "humedad",
                "RadiacionSolar": "radiacion_solar",
            }
        ).copy()

        faltantes = [columna for columna in self.COLUMNAS_SALIDA if columna not in df.columns]
        if faltantes:
            raise ValueError(f"Columnas faltantes para transformar clima: {', '.join(faltantes)}")

        df["zona"] = df["zona"].astype(str).str.upper().str.strip()
        df["anio"] = pd.to_numeric(df["anio"], errors="coerce").astype("Int64")
        df["mes"] = pd.to_numeric(df["mes"], errors="coerce").astype("Int64")
        for columna in ("latitud", "longitud", "temp_max", "temp_min", "precipitacion", "humedad", "radiacion_solar"):
            df[columna] = pd.to_numeric(df[columna], errors="coerce")
        df["latitud"] = df["latitud"].round(6)
        df["longitud"] = df["longitud"].round(6)

        df = df.dropna(subset=["zona", "anio", "mes"])
        df = df.dropna(
            subset=["latitud", "longitud", "temp_max", "temp_min", "precipitacion", "humedad", "radiacion_solar"],
            how="any",
        )
        return df[self.COLUMNAS_SALIDA].reset_index(drop=True)
