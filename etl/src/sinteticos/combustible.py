from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import math
from typing import Iterator

from admin_db_conn.db import SqlServerDB


FUENTE_SINTETICA_COMBUSTIBLE = 6


@dataclass(slots=True)
class ResumenCombustibleSintetico:
    total_registros: int
    total_productos: int
    total_fechas: int


class GeneradorCombustibleSintetico:
    def __init__(
        self,
        total_registros: int = 2_000_000,
        total_productos: int = 2_000,
        fecha_inicio: date = date(2024, 1, 1),
        tamano_lote: int = 100_000,
    ) -> None:
        if total_registros <= 0:
            raise ValueError("El total de registros sinteticos debe ser mayor a cero.")
        if total_productos <= 0:
            raise ValueError("La cantidad de productos sinteticos debe ser mayor a cero.")
        if tamano_lote <= 0:
            raise ValueError("El tamano de lote debe ser mayor a cero.")

        self.total_registros = total_registros
        self.total_productos = total_productos
        self.fecha_inicio = fecha_inicio
        self.tamano_lote = tamano_lote
        self.total_fechas = math.ceil(total_registros / total_productos)

    def resumen(self) -> ResumenCombustibleSintetico:
        return ResumenCombustibleSintetico(
            total_registros=self.total_registros,
            total_productos=self.total_productos,
            total_fechas=self.total_fechas,
        )

    def construir_productos(self) -> list[tuple[str, str, str, str, str, int, float, float, int]]:
        productos: list[tuple[str, str, str, str, str, int, float, float, int]] = []
        for indice in range(self.total_productos):
            nombre = self._nombre_producto(indice)
            productos.append(
                (
                    nombre,
                    nombre,
                    "Combustibles",
                    "Hidrocarburos Sinteticos",
                    "Litro",
                    FUENTE_SINTETICA_COMBUSTIBLE,
                    self._precio_base_referencia(indice),
                    1.0,
                    indice % 2,
                )
            )
        return productos

    def construir_fechas(self) -> list[tuple[int, str, int, int, str, int, int]]:
        fechas: list[tuple[int, str, int, int, str, int, int]] = []
        for desplazamiento in range(self.total_fechas):
            fecha = self.fecha_inicio + timedelta(days=desplazamiento)
            fechas.append(
                (
                    int(fecha.strftime("%Y%m%d")),
                    fecha.strftime("%Y-%m-%d"),
                    fecha.day,
                    fecha.month,
                    fecha.strftime("%B"),
                    fecha.year,
                    ((fecha.month - 1) // 3) + 1,
                )
            )
        return fechas

    def iterar_lotes_precios(self) -> Iterator[list[tuple[str, str, float, int]]]:
        lote_actual: list[tuple[str, str, float, int]] = []
        registros_restantes = self.total_registros

        for indice_fecha in range(self.total_fechas):
            fecha = self.fecha_inicio + timedelta(days=indice_fecha)
            fecha_raw = fecha.strftime("%Y-%m-%dT00:00:00")
            productos_en_fecha = min(self.total_productos, registros_restantes)

            for indice_producto in range(productos_en_fecha):
                lote_actual.append(
                    (
                        fecha_raw,
                        self._nombre_producto(indice_producto),
                        self._precio(indice_producto, indice_fecha),
                        FUENTE_SINTETICA_COMBUSTIBLE,
                    )
                )
                if len(lote_actual) >= self.tamano_lote:
                    yield lote_actual
                    lote_actual = []

            registros_restantes -= productos_en_fecha
            if registros_restantes <= 0:
                break

        if lote_actual:
            yield lote_actual

    @staticmethod
    def _nombre_producto(indice: int) -> str:
        return f"COMBUSTIBLE SINTETICO {indice + 1:04d}"

    @staticmethod
    def _precio_base_referencia(indice: int) -> float:
        return round(430.0 + ((indice % 50) * 7.25), 2)

    @staticmethod
    def _precio(indice_producto: int, indice_fecha: int) -> float:
        base = 430.0 + ((indice_producto % 50) * 7.25)
        variacion_producto = (indice_producto % 17) * 0.61
        variacion_fecha = (indice_fecha % 31) * 0.83
        tendencia = (indice_fecha // 30) * 0.15
        return round(base + variacion_producto + variacion_fecha + tendencia, 2)


class CargadorCombustibleSintetico:
    def __init__(self, db: SqlServerDB) -> None:
        self.db = db

    def cargar_staging(self, generador: GeneradorCombustibleSintetico) -> ResumenCombustibleSintetico:
        resumen = generador.resumen()

        with self.db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM dbo.StagingPrecioGasolina WHERE FuenteID = ?",
                (FUENTE_SINTETICA_COMBUSTIBLE,),
            )
            cursor.execute(
                "DELETE FROM dbo.StagingProducto WHERE FuenteID = ?",
                (FUENTE_SINTETICA_COMBUSTIBLE,),
            )
            conn.commit()

            cursor.fast_executemany = True
            cursor.executemany(
                """
                INSERT INTO dbo.StagingProducto (
                    NombreRaw,
                    NombreNormalizado,
                    Categoria,
                    SubCategoria,
                    UnidadMedida,
                    FuenteID,
                    PrecioBaseReferencia,
                    FactorCanasta,
                    EsImportado
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                generador.construir_productos(),
            )
            conn.commit()

            for fecha_id, fecha, dia, mes, nombre_mes, anio, trimestre in generador.construir_fechas():
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
                        fecha_id,
                        fecha_id,
                        fecha,
                        dia,
                        mes,
                        nombre_mes,
                        anio,
                        trimestre,
                    ),
                )
            conn.commit()

            cursor.fast_executemany = True
            for lote in generador.iterar_lotes_precios():
                cursor.executemany(
                    """
                    INSERT INTO dbo.StagingPrecioGasolina (
                        FechaRaw,
                        NombreProductoRaw,
                        Precio,
                        FuenteID
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    lote,
                )
                conn.commit()

        return resumen
