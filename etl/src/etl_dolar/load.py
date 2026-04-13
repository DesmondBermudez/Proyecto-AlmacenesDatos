from __future__ import annotations

from admin_db_conn.db import SqlServerDB
from etl_dolar.models import RegistroTipoCambio


class CargadorDolar:
    def __init__(self, db: SqlServerDB) -> None:
        self.db = db

    def cargar_staging(self, registros: list[RegistroTipoCambio]) -> None:
        registros_unicos = list(
            {
                (
                    registro.fecha,
                    registro.moneda_base_id,
                    registro.moneda_referencia_id,
                ): registro
                for registro in registros
            }.values()
        )
        fechas_unicas = sorted({registro.fecha for registro in registros_unicos})

        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.fast_executemany = True
            cursor.executemany(
                """
                IF NOT EXISTS (SELECT 1 FROM dbo.StagingFecha WHERE FechaID = ?)
                BEGIN
                    INSERT INTO dbo.StagingFecha (
                        FechaID, Fecha, Dia, Mes, NombreMes, Trimestre, Anio
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                END
                """,
                [
                    (
                        int(fecha.strftime("%Y%m%d")),
                        int(fecha.strftime("%Y%m%d")),
                        fecha.strftime("%Y-%m-%d"),
                        fecha.day,
                        fecha.month,
                        fecha.strftime("%B"),
                        ((fecha.month - 1) // 3) + 1,
                        fecha.year,
                    )
                    for fecha in fechas_unicas
                ],
            )
            cursor.executemany(
                """
                INSERT INTO dbo.StagingTipoCambio (
                    Fecha,
                    FechaID,
                    MonedaBaseID,
                    MonedaReferenciaID,
                    FuenteID,
                    TipoCambioCompra,
                    TipoCambioVenta,
                    TipoCambioPromedio
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        registro.fecha.strftime("%Y-%m-%d"),
                        int(registro.fecha.strftime("%Y%m%d")),
                        registro.moneda_base_id,
                        registro.moneda_referencia_id,
                        registro.fuente_id,
                        registro.compra,
                        registro.venta,
                        (registro.compra + registro.venta) / 2.0,
                    )
                    for registro in registros_unicos
                ],
            )
            conn.commit()
