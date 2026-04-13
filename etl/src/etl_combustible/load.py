from __future__ import annotations

import pandas as pd

from admin_db_conn.db import SqlServerDB
from etl_combustible.models import RegistroPrecioCombustible, RegistroProductoCombustible


class CargadorCombustible:
    def __init__(self, db: SqlServerDB) -> None:
        self.db = db

    def cargar_staging(
        self,
        productos: list[RegistroProductoCombustible],
        precios: list[RegistroPrecioCombustible],
    ) -> None:
        productos_unicos = list(
            {
                (
                    producto.nombre_raw,
                    producto.nombre_normalizado,
                    producto.categoria,
                    producto.subcategoria,
                    producto.unidad_medida,
                    producto.fuente_id,
                ): producto
                for producto in productos
            }.values()
        )
        precios_unicos = list(
            {
                (
                    precio.fecha_raw,
                    precio.nombre_producto_raw,
                    precio.precio,
                    precio.fuente_id,
                ): precio
                for precio in precios
            }.values()
        )

        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM dbo.StagingProducto
                WHERE Categoria = 'Combustibles' AND SubCategoria = 'Hidrocarburos'
                """
            )
            cursor.execute("DELETE FROM dbo.StagingPrecioGasolina")
            for producto in productos_unicos:
                cursor.execute(
                    """
                    INSERT INTO dbo.StagingProducto (
                        NombreRaw, NombreNormalizado, Categoria, SubCategoria, UnidadMedida,
                        FuenteID, PrecioBaseReferencia, FactorCanasta, EsImportado
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        0,
                    ),
                )

            for precio in precios_unicos:
                fecha_precio = pd.to_datetime(str(precio.fecha_raw)[:10], errors="coerce")
                if pd.notna(fecha_precio):
                    fecha_python = fecha_precio.to_pydatetime()
                    fecha_id = int(fecha_precio.strftime("%Y%m%d"))
                    cursor.execute(
                        """
                        IF NOT EXISTS (
                            SELECT 1 FROM dbo.StagingFecha WHERE FechaID = ?
                        )
                        BEGIN
                            INSERT INTO dbo.StagingFecha (
                                FechaID, Fecha, Dia, Mes, NombreMes, Anio, Trimestre
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        END
                        """,
                        (
                            fecha_id,
                            fecha_id,
                            fecha_precio.strftime("%Y-%m-%d"),
                            fecha_python.day,
                            fecha_python.month,
                            fecha_precio.strftime("%B"),
                            fecha_python.year,
                            ((fecha_python.month - 1) // 3) + 1,
                        ),
                    )

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
