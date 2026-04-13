from __future__ import annotations

from admin_db_conn.db import SqlServerDB


class CoordinadorDW:
    def __init__(self, db: SqlServerDB) -> None:
        self.db = db

    def limpiar_staging(self) -> None:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            for tabla in (
                "dbo.StagingClimaMensual",
                "dbo.StagingZonaClimatica",
                "dbo.StagingInec",
                "dbo.StagingPrecioGasolina",
                "dbo.StagingProducto",
                "dbo.StagingTipoCambio",
                "dbo.StagingFecha",
            ):
                cursor.execute(f"DELETE FROM {tabla}")
            conn.commit()

    def asegurar_catalogos_base(self) -> None:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            for fuente_id, nombre, descripcion in (
                (1, "Ministerio de Hacienda CR", "MHCR"),
                (2, "ARESEP", "ARSP"),
                (3, "Respaldo local o simulado", "RESPALDO"),
                (4, "NASA POWER", "NASA_POWER"),
                (5, "INEC", "INEC"),
                (6, "Generador sintetico de combustible", "SINTETICO"),
            ):
                cursor.execute(
                    """
                    IF NOT EXISTS (SELECT 1 FROM dbo.DimFuenteDatos WHERE FuenteID = ?)
                    BEGIN
                        SET IDENTITY_INSERT dbo.DimFuenteDatos ON;
                        INSERT INTO dbo.DimFuenteDatos (FuenteID, NombreFuente, Descripcion)
                        VALUES (?, ?, ?);
                        SET IDENTITY_INSERT dbo.DimFuenteDatos OFF;
                    END
                    """,
                    (fuente_id, fuente_id, nombre, descripcion),
                )
                cursor.execute(
                    """
                    UPDATE dbo.DimFuenteDatos
                    SET NombreFuente = ?, Descripcion = ?
                    WHERE FuenteID = ?
                    """,
                    (nombre, descripcion, fuente_id),
                )

            for moneda_id, nombre, codigo in (
                (1, "Dolar Americano", "USD"),
                (2, "Colon Costarricense", "CRC"),
            ):
                cursor.execute(
                    """
                    IF NOT EXISTS (SELECT 1 FROM dbo.DimMoneda WHERE MonedaID = ?)
                    BEGIN
                        SET IDENTITY_INSERT dbo.DimMoneda ON;
                        INSERT INTO dbo.DimMoneda (MonedaID, NombreMoneda, CodigoMoneda)
                        VALUES (?, ?, ?);
                        SET IDENTITY_INSERT dbo.DimMoneda OFF;
                    END
                    """,
                    (moneda_id, moneda_id, nombre, codigo),
                )
            conn.commit()

    def ejecutar_transformaciones_dw(self) -> None:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            for procedimiento in (
                "EXEC dbo.sp_Transform_DimFecha",
                "EXEC dbo.sp_Transform_DimProducto",
                "EXEC dbo.sp_Transform_DimZonaCBA",
                "EXEC dbo.sp_Transform_DimCategoriaCBA",
                "EXEC dbo.sp_Transform_DimZonaClimatica",
                "EXEC dbo.sp_Transform_FactTipoCambio",
                "EXEC dbo.sp_Load_FactPrecioCombustible",
                "EXEC dbo.sp_Load_FactCanastaInecOficial",
                "EXEC dbo.sp_Load_FactClimaMensual",
            ):
                cursor.execute(procedimiento)
            conn.commit()

    def ejecutar_transformaciones_combustible(self) -> None:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            for procedimiento in (
                "EXEC dbo.sp_Transform_DimFecha",
                "EXEC dbo.sp_Transform_DimProducto",
                "EXEC dbo.sp_Load_FactPrecioCombustible",
            ):
                cursor.execute(procedimiento)
            conn.commit()

    def contar_fact_precio_combustible(self, fuente_id: int | None = None) -> int:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            if fuente_id is None:
                cursor.execute("SELECT COUNT(*) FROM dbo.FactPrecioCombustible")
            else:
                cursor.execute(
                    "SELECT COUNT(*) FROM dbo.FactPrecioCombustible WHERE FuenteID = ?",
                    (fuente_id,),
                )
            return int(cursor.fetchone()[0])
