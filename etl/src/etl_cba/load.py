from __future__ import annotations

import pandas as pd

from admin_db_conn.db import SqlServerDB


class CargadorCBA:
    def __init__(self, db: SqlServerDB) -> None:
        self.db = db

    def cargar_staging(self, dataframe: pd.DataFrame) -> None:
        df = dataframe.copy()
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.strftime("%Y-%m-%d")
        df["FechaID"] = pd.to_numeric(df["FechaID"], errors="coerce").astype("Int64")
        df["CostoPerCapita"] = pd.to_numeric(df["CostoPerCapita"], errors="coerce")
        df["FuenteID"] = pd.to_numeric(df["FuenteID"], errors="coerce").astype("Int64")
        df = df.drop_duplicates(subset=["FechaID", "Zona", "CategoriaNombre"], keep="last")
        df = df.dropna(
            subset=[
                "Fecha",
                "FechaID",
                "Zona",
                "CategoriaNombre",
                "PeriodoTextoOriginal",
                "CostoPerCapita",
                "ArchivoOrigen",
                "FuenteID",
            ]
        )

        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM dbo.StagingInec")
            conn.commit()

            fechas = df[["Fecha", "FechaID"]].drop_duplicates().sort_values(by="Fecha")
            for _, row in fechas.iterrows():
                fecha = pd.Timestamp(row["Fecha"]).to_pydatetime()
                cursor.execute(
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
                    (
                        int(row["FechaID"]),
                        int(row["FechaID"]),
                        fecha.strftime("%Y-%m-%d"),
                        fecha.day,
                        fecha.month,
                        fecha.strftime("%B"),
                        fecha.year,
                        ((fecha.month - 1) // 3) + 1,
                    ),
                )
            conn.commit()

            cursor.fast_executemany = True
            lote = [
                (
                    fila["Fecha"],
                    int(fila["FechaID"]),
                    fila["Zona"],
                    fila["CategoriaNombre"],
                    fila["PeriodoTextoOriginal"],
                    float(fila["CostoPerCapita"]),
                    fila["ArchivoOrigen"],
                    int(fila["FuenteID"]),
                )
                for _, fila in df.iterrows()
            ]
            cursor.executemany(
                """
                INSERT INTO dbo.StagingInec (
                    Fecha,
                    FechaID,
                    Zona,
                    CategoriaNombre,
                    PeriodoTextoOriginal,
                    CostoPerCapita,
                    ArchivoOrigen,
                    FuenteID
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                lote,
            )
            conn.commit()
