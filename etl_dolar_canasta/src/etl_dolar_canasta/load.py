from __future__ import annotations

import pandas as pd

from etl_dolar_canasta.db import SqlServerDB
from etl_dolar_canasta.models import (
    FUENTE_RESPALDO,
    RegistroPrecioCombustible,
    RegistroProductoCombustible,
    RegistroTipoCambio,
)


class CargadorDW:
    def __init__(self, db: SqlServerDB) -> None:
        self.db = db

    def asegurar_catalogos_base(self) -> None:
        with self.db.connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                IF NOT EXISTS (SELECT 1 FROM dbo.DimFuenteDatos WHERE FuenteID = 1)
                BEGIN
                    SET IDENTITY_INSERT dbo.DimFuenteDatos ON;
                    INSERT INTO dbo.DimFuenteDatos (FuenteID, NombreFuente, Descripcion)
                    VALUES (1, 'Ministerio de Hacienda CR', 'MHCR');
                    SET IDENTITY_INSERT dbo.DimFuenteDatos OFF;
                END
                """
            )
            cursor.execute(
                """
                IF NOT EXISTS (SELECT 1 FROM dbo.DimFuenteDatos WHERE FuenteID = 2)
                BEGIN
                    SET IDENTITY_INSERT dbo.DimFuenteDatos ON;
                    INSERT INTO dbo.DimFuenteDatos (FuenteID, NombreFuente, Descripcion)
                    VALUES (2, 'Aresep', 'ARSP');
                    SET IDENTITY_INSERT dbo.DimFuenteDatos OFF;
                END
                """
            )
            cursor.execute(
                """
                IF NOT EXISTS (SELECT 1 FROM dbo.DimFuenteDatos WHERE FuenteID = 3)
                BEGIN
                    SET IDENTITY_INSERT dbo.DimFuenteDatos ON;
                    INSERT INTO dbo.DimFuenteDatos (FuenteID, NombreFuente, Descripcion)
                    VALUES (3, 'Respaldo local o simulado', 'RESPALDO');
                    SET IDENTITY_INSERT dbo.DimFuenteDatos OFF;
                END
                """
            )
            cursor.execute(
                """
                UPDATE dbo.DimFuenteDatos
                SET NombreFuente = 'Respaldo local o simulado',
                    Descripcion = 'RESPALDO'
                WHERE FuenteID = 3
                """
            )

            cursor.execute(
                """
                IF NOT EXISTS (SELECT 1 FROM dbo.DimMoneda WHERE MonedaID = 1)
                BEGIN
                    SET IDENTITY_INSERT dbo.DimMoneda ON;
                    INSERT INTO dbo.DimMoneda (MonedaID, NombreMoneda, CodigoMoneda)
                    VALUES (1, 'Dolar Americano', 'USD');
                    SET IDENTITY_INSERT dbo.DimMoneda OFF;
                END
                """
            )
            cursor.execute(
                """
                IF NOT EXISTS (SELECT 1 FROM dbo.DimMoneda WHERE MonedaID = 2)
                BEGIN
                    SET IDENTITY_INSERT dbo.DimMoneda ON;
                    INSERT INTO dbo.DimMoneda (MonedaID, NombreMoneda, CodigoMoneda)
                    VALUES (2, 'Colon Costarricense', 'CRC');
                    SET IDENTITY_INSERT dbo.DimMoneda OFF;
                END
                """
            )
            conn.commit()

    def cargar_tipo_cambio(self, registros: list[RegistroTipoCambio]) -> None:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            for registro in registros:
                cursor.execute(
                    """
                    EXEC dbo.sp_InsertarTipoCambioStaging
                        @Fecha=?,
                        @Compra=?,
                        @Venta=?,
                        @MonedaBaseID=?,
                        @MonedaRefID=?,
                        @FuenteID=?
                    """,
                    (
                        registro.fecha.strftime("%Y-%m-%d"),
                        registro.compra,
                        registro.venta,
                        registro.moneda_base_id,
                        registro.moneda_referencia_id,
                        registro.fuente_id,
                    ),
                )
            conn.commit()

    def cargar_combustibles(
        self,
        productos: list[RegistroProductoCombustible],
        precios: list[RegistroPrecioCombustible],
    ) -> None:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM dbo.StagingProducto
                WHERE Categoria = 'Combustibles' AND SubCategoria = 'Hidrocarburos'
                """
            )
            cursor.execute("DELETE FROM dbo.StagingPrecioGasolina")
            for producto in productos:
                cursor.execute(
                    """
                    INSERT INTO dbo.StagingProducto (
                        NombreRaw, NombreNormalizado, Categoria, SubCategoria, UnidadMedida,
                        FuenteID, PrecioBaseReferencia, FactorCanasta
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        producto.nombre_raw,
                        producto.nombre_normalizado,
                        producto.categoria,
                        producto.subcategoria,
                        producto.unidad_medida,
                        producto.fuente_id,
                        0.0,
                        1.0,
                    ),
                )
            for precio in precios:
                cursor.execute(
                    """
                    INSERT INTO dbo.StagingPrecioGasolina (
                        FechaRaw, NombreProductoRaw, Precio, FuenteID
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        precio.fecha_raw,
                        precio.nombre_producto_raw,
                        precio.precio,
                        precio.fuente_id,
                    ),
                )
            conn.commit()

    def cargar_canasta(self, dataframe: pd.DataFrame) -> None:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM dbo.StagingProducto WHERE FuenteID = {FUENTE_RESPALDO}")
            cursor.execute(
                f"DELETE FROM dbo.StagingHistoricoCanasta WHERE FuenteID = {FUENTE_RESPALDO}"
            )
            conn.commit()

            productos_unicos = (
                dataframe.groupby("NombreProducto", as_index=False)
                .agg(
                    {
                        "Categoria": "first",
                        "UnidadMedida": "first",
                        "EsImportado": "first",
                        "PrecioBaseReferencia": "first",
                        "FactorCanasta": "mean",
                    }
                )
            )
            for _, row in productos_unicos.iterrows():
                cursor.execute(
                    """
                    IF NOT EXISTS (
                        SELECT 1 FROM dbo.StagingProducto WHERE NombreRaw = ? AND FuenteID = ?
                    )
                    BEGIN
                        INSERT INTO dbo.StagingProducto (
                            NombreRaw, NombreNormalizado, Categoria, SubCategoria, UnidadMedida,
                            EsImportado, FuenteID, PrecioBaseReferencia, FactorCanasta
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    END
                    """,
                    (
                        row["NombreProducto"],
                        FUENTE_RESPALDO,
                        row["NombreProducto"],
                        row["NombreProducto"],
                        row["Categoria"],
                        row["Categoria"],
                        row["UnidadMedida"],
                        int(row["EsImportado"]),
                        FUENTE_RESPALDO,
                        float(row["PrecioBaseReferencia"]),
                        float(row["FactorCanasta"]),
                    ),
                )

            fechas_unicas = pd.to_datetime(dataframe["Fecha"]).drop_duplicates().sort_values()
            for fecha in fechas_unicas:
                fecha_python = fecha.to_pydatetime()
                fecha_id = int(fecha.strftime("%Y%m%d"))
                cursor.execute(
                    """
                    IF NOT EXISTS (
                        SELECT 1 FROM dbo.StagingFecha WHERE FechaID = ?
                    )
                    BEGIN
                        INSERT INTO dbo.StagingFecha (
                            FechaID, Fecha, Dia, Mes, NombreMes, Año, Trimestre
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    END
                    """,
                    (
                        fecha_id,
                        fecha_id,
                        fecha.strftime("%Y-%m-%d"),
                        fecha_python.day,
                        fecha_python.month,
                        fecha.strftime("%B"),
                        fecha_python.year,
                        ((fecha_python.month - 1) // 3) + 1,
                    ),
                )

            conn.commit()
            cursor.fast_executemany = True
            lote = [
                (
                    fila["Fecha"],
                    fila["NombreProducto"],
                    fila["Provincia"],
                    fila["Canton"],
                    fila["Distrito"],
                    float(fila["PrecioColones"]),
                    FUENTE_RESPALDO,
                )
                for _, fila in dataframe.iterrows()
            ]
            cursor.executemany(
                """
                INSERT INTO dbo.StagingHistoricoCanasta (
                    Fecha, NombreProductoRaw, Provincia, Canton, Distrito, PrecioColones, FuenteID
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                lote,
            )
            conn.commit()

    def ejecutar_transformaciones_dw(self) -> None:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("EXEC dbo.sp_Transform_DimFecha")
            cursor.execute("EXEC dbo.sp_Transform_DimProducto")
            cursor.execute("EXEC dbo.sp_Transform_DimRegion")
            cursor.execute("EXEC dbo.sp_Transform_FactTipoCambio")
            cursor.execute("EXEC dbo.sp_Load_FactPreciosCanasta")
            conn.commit()
