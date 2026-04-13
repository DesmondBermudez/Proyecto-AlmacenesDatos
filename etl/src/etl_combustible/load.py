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
            cursor.fast_executemany = True
            cursor.executemany(
                """
                INSERT INTO dbo.StagingProducto (
                    NombreRaw, NombreNormalizado, Categoria, SubCategoria, UnidadMedida,
                    FuenteID, PrecioBaseReferencia, FactorCanasta, EsImportado
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
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
                    )
                    for producto in productos_unicos
                ],
            )

            fechas_precio = sorted(
                {
                    fecha_precio.normalize()
                    for precio in precios_unicos
                    for fecha_precio in [pd.to_datetime(str(precio.fecha_raw)[:10], errors="coerce")]
                    if pd.notna(fecha_precio)
                }
            )
            cursor.executemany(
                """
                IF NOT EXISTS (SELECT 1 FROM dbo.StagingFecha WHERE FechaID = ?)
                BEGIN
                    INSERT INTO dbo.StagingFecha (
                        FechaID, Fecha, Dia, Mes, NombreMes, Anio, Trimestre
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
                        fecha.year,
                        ((fecha.month - 1) // 3) + 1,
                    )
                    for fecha in fechas_precio
                ],
            )

            cursor.executemany(
                """
                INSERT INTO dbo.StagingPrecioGasolina (
                    FechaRaw, NombreProductoRaw, Precio, FuenteID
                ) VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        precio.fecha_raw,
                        precio.nombre_producto_raw,
                        precio.precio,
                        precio.fuente_id,
                    )
                    for precio in precios_unicos
                ],
            )
            conn.commit()
