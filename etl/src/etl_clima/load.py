from __future__ import annotations

from pathlib import Path

import pandas as pd

from admin_db_conn.db import SqlServerDB
from etl_clima.models import FUENTE_NASA


class CargadorClima:
    def __init__(
        self,
        ruta_salida_csv: Path | None = None,
        db: SqlServerDB | None = None,
    ) -> None:
        self.ruta_salida_csv = ruta_salida_csv
        self.db = db

    def guardar_csv(self, dataframe: pd.DataFrame) -> Path:
        if self.ruta_salida_csv is None:
            raise ValueError("Se requiere una ruta de salida para guardar el CSV de clima.")
        self.ruta_salida_csv.parent.mkdir(parents=True, exist_ok=True)
        dataframe.to_csv(self.ruta_salida_csv, index=False, encoding="utf-8-sig")
        return self.ruta_salida_csv

    def cargar_staging(self, dataframe: pd.DataFrame) -> None:
        if self.db is None:
            raise ValueError("Se requiere una conexion SQL Server para cargar staging de clima.")

        df = dataframe.copy()
        df = df.dropna(
            subset=[
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
        ).copy()
        df["latitud"] = pd.to_numeric(df["latitud"], errors="raise").round(6)
        df["longitud"] = pd.to_numeric(df["longitud"], errors="raise").round(6)
        df["Fecha"] = pd.to_datetime(
            {
                "year": pd.to_numeric(df["anio"], errors="raise").astype(int),
                "month": pd.to_numeric(df["mes"], errors="raise").astype(int),
                "day": 1,
            }
        )
        df["FechaID"] = df["Fecha"].dt.strftime("%Y%m%d").astype(int)
        df = df.drop_duplicates(subset=["FechaID", "zona", "latitud", "longitud"], keep="last")

        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM dbo.StagingClimaMensual WHERE FuenteID = ?", (FUENTE_NASA,))
            cursor.execute("DELETE FROM dbo.StagingZonaClimatica WHERE FuenteID = ?", (FUENTE_NASA,))
            conn.commit()

            zonas = df[["zona", "latitud", "longitud"]].drop_duplicates()
            cursor.fast_executemany = True
            cursor.executemany(
                """
                IF NOT EXISTS (
                    SELECT 1
                    FROM dbo.StagingZonaClimatica
                    WHERE NombreZona = ? AND Latitud = ? AND Longitud = ? AND FuenteID = ?
                )
                BEGIN
                    INSERT INTO dbo.StagingZonaClimatica (
                        NombreZona,
                        Latitud,
                        Longitud,
                        FuenteID
                    )
                    VALUES (?, ?, ?, ?)
                END
                """,
                [
                    (
                        zona,
                        float(latitud),
                        float(longitud),
                        FUENTE_NASA,
                        zona,
                        float(latitud),
                        float(longitud),
                        FUENTE_NASA,
                    )
                    for zona, latitud, longitud in zonas.itertuples(index=False, name=None)
                ],
            )

            fechas = df[["Fecha", "FechaID"]].drop_duplicates().sort_values(by="Fecha")
            cursor.executemany(
                """
                IF NOT EXISTS (
                    SELECT 1 FROM dbo.StagingFecha WHERE FechaID = ?
                )
                BEGIN
                    INSERT INTO dbo.StagingFecha (
                        FechaID,
                        Fecha,
                        Dia,
                        Mes,
                        NombreMes,
                        Anio,
                        Trimestre
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                END
                """,
                [
                    (
                        int(fecha_id),
                        int(fecha_id),
                        fecha.strftime("%Y-%m-%d"),
                        fecha.day,
                        fecha.month,
                        fecha.strftime("%B"),
                        fecha.year,
                        ((fecha.month - 1) // 3) + 1,
                    )
                    for fecha, fecha_id in fechas.itertuples(index=False, name=None)
                    for fecha in [pd.Timestamp(fecha).to_pydatetime()]
                ],
            )
            conn.commit()

            lote = [
                (
                    fila["Fecha"].strftime("%Y-%m-%d"),
                    int(fila["FechaID"]),
                    fila["zona"],
                    float(fila["latitud"]),
                    float(fila["longitud"]),
                    None if pd.isna(fila["temp_max"]) else float(fila["temp_max"]),
                    None if pd.isna(fila["temp_min"]) else float(fila["temp_min"]),
                    None if pd.isna(fila["precipitacion"]) else float(fila["precipitacion"]),
                    None if pd.isna(fila["humedad"]) else float(fila["humedad"]),
                    None if pd.isna(fila["radiacion_solar"]) else float(fila["radiacion_solar"]),
                    FUENTE_NASA,
                )
                for fila in df.to_dict(orient="records")
            ]
            cursor.executemany(
                """
                INSERT INTO dbo.StagingClimaMensual (
                    Fecha,
                    FechaID,
                    NombreZona,
                    Latitud,
                    Longitud,
                    TempMax,
                    TempMin,
                    Precipitacion,
                    Humedad,
                    RadiacionSolar,
                    FuenteID
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                lote,
            )
            conn.commit()
