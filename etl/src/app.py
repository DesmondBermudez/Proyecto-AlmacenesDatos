from __future__ import annotations

from pathlib import Path
import time

import pandas as pd

from admin_db_conn.config import ParametrosETL
from admin_db_conn.db import SqlServerDB
from etl_clima.extract import ExtractorClimaNASA
from etl_clima.load import CargadorClima
from etl_clima.transform import TransformadorClima
from etl_dolar_canasta.combustibles import (
    clasificar_producto_combustible,
    es_registro_combustible_utilizable,
)
from etl_dolar_canasta.extract import ExtractorCombustible, ExtractorTipoCambio, GeneradorCanasta
from etl_dolar_canasta.load import CargadorDW
from etl_dolar_canasta.transform import TransformadorCanasta, TransformadorCombustible
from runtime import formatear_duracion
from trazabilidad import (
    ValidadorTrazabilidad,
    auditar_tabla_sql_no_nulos,
    validar_columnas_obligatorias,
)


class ETLDolarCanastaApp:
    def __init__(self, parametros: ParametrosETL, base_dir: Path) -> None:
        self.parametros = parametros
        self.base_dir = base_dir
        self.raw_data_dir = base_dir / "etl" / "data" / "raw"
        self.db = SqlServerDB(parametros)
        self.cargador = CargadorDW(self.db)
        self.extractor_tipo_cambio = ExtractorTipoCambio(
            self.raw_data_dir / "tipo_cambio_historico.csv"
        )
        self.extractor_combustible = ExtractorCombustible(
            self.raw_data_dir / "combustible_historico.csv"
        )
        self.generador_canasta = GeneradorCanasta(
            self.raw_data_dir / "historico_canasta_cr.csv"
        )
        self.extractor_clima = ExtractorClimaNASA(
            ruta_respaldo_csv=self.raw_data_dir / "clima_historico.csv"
        )
        self.cargador_clima = CargadorClima(
            ruta_salida_csv=self.raw_data_dir / "clima_historico.csv",
            db=self.db,
        )
        self.transformador_combustible = TransformadorCombustible()
        self.transformador_canasta = TransformadorCanasta()
        self.transformador_clima = TransformadorClima()
        self._inicio_flujo = 0.0
        self._validadores: dict[str, ValidadorTrazabilidad] = {}
        self._estadisticas: dict[str, dict[str, int]] = {}

    def ejecutar(self) -> int:
        print("=" * 50)
        print("ETL - TIPO DE CAMBIO, COMBUSTIBLES, CANASTA Y CLIMA")
        print("=" * 50)
        self._inicio_flujo = time.perf_counter()
        guardar_historicos = self.parametros.es_historico or self.parametros.generar_historicos

        try:
            self._ejecutar_etapa("Limpieza de staging", self.cargador.limpiar_staging)

            if self.parametros.es_historico:
                print("Modo historico")
                registros_tc = self._ejecutar_etapa(
                    "Extraccion tipo de cambio historico",
                    lambda: self.extractor_tipo_cambio.obtener_historico(
                        guardar_csv=guardar_historicos,
                        sobrescribir_csv=True,
                    ),
                )
            else:
                print("Modo direct-insert")
                registros_tc = self._ejecutar_etapa(
                    "Extraccion tipo de cambio diario",
                    lambda: [
                        self.extractor_tipo_cambio.obtener_diario(
                            guardar_csv=guardar_historicos,
                            sobrescribir_csv=False,
                        )
                    ],
                )

            self._trazar_tipo_cambio(registros_tc, registrar_csv=guardar_historicos)
            self._ejecutar_etapa(
                "Carga staging tipo de cambio",
                lambda: self.cargador.cargar_tipo_cambio(registros_tc),
            )
            perfil_tc_staging = self._validadores["tipo_cambio"].registrar_sql(
                "staging",
                self.db,
                """
                SELECT
                    CONVERT(VARCHAR(10), Fecha, 23) AS fecha,
                    TipoCambioCompra AS compra,
                    TipoCambioVenta AS venta
                FROM dbo.StagingTipoCambio
                """,
            )
            self._actualizar_estadisticas("tipo_cambio", staging=perfil_tc_staging.filas)

            registros_combustible = self._ejecutar_etapa(
                "Extraccion combustibles",
                lambda: self.extractor_combustible.obtener(
                    guardar_csv=guardar_historicos,
                    sobrescribir_csv=self.parametros.es_historico,
                ),
            )
            registros_combustible = self._depurar_registros_combustible(registros_combustible)
            productos, precios = self._ejecutar_etapa(
                "Transformacion combustibles",
                lambda: self.transformador_combustible.transformar(registros_combustible),
            )
            self._trazar_combustibles(productos, precios, registrar_csv=guardar_historicos)
            self._ejecutar_etapa(
                "Carga staging combustibles",
                lambda: self.cargador.cargar_combustibles(productos, precios),
            )
            perfil_comb_staging = self._validadores["combustible_precios"].registrar_sql(
                "staging",
                self.db,
                """
                SELECT
                    LEFT(FechaRaw, 10) AS fecha,
                    TRIM(UPPER(NombreProductoRaw)) AS producto,
                    Precio AS precio
                FROM dbo.StagingPrecioGasolina
                WHERE Precio IS NOT NULL
                """,
            )
            self._actualizar_estadisticas("combustibles", staging=perfil_comb_staging.filas)

            ruta_canasta = self._ejecutar_etapa(
                "Generacion historico canasta",
                self.generador_canasta.generar,
            )
            df_canasta = self._ejecutar_etapa(
                "Transformacion canasta",
                lambda: self.transformador_canasta.leer_y_transformar(ruta_canasta),
            )
            self._trazar_canasta(ruta_canasta, df_canasta)
            self._ejecutar_etapa(
                "Carga staging canasta",
                lambda: self.cargador.cargar_canasta(df_canasta),
            )
            perfil_canasta_staging = self._validadores["canasta"].registrar_sql(
                "staging",
                self.db,
                """
                SELECT
                    CONVERT(VARCHAR(10), Fecha, 23) AS fecha,
                    TRIM(UPPER(NombreProductoRaw)) AS producto,
                    TRIM(UPPER(Provincia)) AS provincia,
                    TRIM(UPPER(Canton)) AS canton,
                    TRIM(UPPER(Distrito)) AS distrito,
                    PrecioColones AS precio
                FROM dbo.StagingHistoricoCanasta
                """,
            )
            self._actualizar_estadisticas("canasta", staging=perfil_canasta_staging.filas)

            df_clima = self._ejecutar_etapa("Extraccion y transformacion clima", self._obtener_clima)
            self._ejecutar_etapa(
                "Carga staging clima",
                lambda: self.cargador_clima.cargar_staging(df_clima),
            )
            perfil_clima_staging = self._validadores["clima"].registrar_sql(
                "staging",
                self.db,
                """
                SELECT
                    TRIM(UPPER(NombreZona)) AS zona,
                    CAST(Latitud AS DECIMAL(9,6)) AS latitud,
                    CAST(Longitud AS DECIMAL(9,6)) AS longitud,
                    FechaID AS fecha_id,
                    TempMax AS temp_max,
                    TempMin AS temp_min,
                    Precipitacion AS precipitacion,
                    Humedad AS humedad,
                    RadiacionSolar AS radiacion_solar
                FROM dbo.StagingClimaMensual
                """,
            )
            self._actualizar_estadisticas("clima", staging=perfil_clima_staging.filas)

            self._ejecutar_etapa("Auditoria de staging", self._auditar_staging_sql)
            self._ejecutar_etapa("Asegurar catalogos base", self.cargador.asegurar_catalogos_base)
            self._ejecutar_etapa(
                "Carga final del DW mediante procedimientos",
                self.cargador.ejecutar_transformaciones_dw,
            )

            perfil_tc_dw = self._validadores["tipo_cambio"].registrar_sql(
                "dw",
                self.db,
                """
                SELECT
                    CONVERT(VARCHAR(10), d.Fecha, 23) AS fecha,
                    f.TipoCambioCompra AS compra,
                    f.TipoCambioVenta AS venta
                FROM dbo.FactTipoCambio f
                INNER JOIN dbo.DimFecha d
                    ON f.FechaID = d.FechaID
                """,
            )
            self._actualizar_estadisticas("tipo_cambio", dw=perfil_tc_dw.filas)

            perfil_comb_dw = self._validadores["combustible_precios"].registrar_sql(
                "dw",
                self.db,
                """
                SELECT
                    CONVERT(VARCHAR(10), d.Fecha, 23) AS fecha,
                    TRIM(UPPER(p.NombreProducto)) AS producto,
                    f.Precio AS precio
                FROM dbo.FactPrecioCombustible f
                INNER JOIN dbo.DimFecha d
                    ON f.FechaID = d.FechaID
                INNER JOIN dbo.DimProducto p
                    ON f.ProductoID = p.ProductoID
                WHERE p.Categoria = 'Combustibles'
                """,
            )
            self._actualizar_estadisticas("combustibles", dw=perfil_comb_dw.filas)

            perfil_canasta_dw = self._validadores["canasta"].registrar_sql(
                "dw",
                self.db,
                """
                SELECT
                    CONVERT(VARCHAR(10), df.Fecha, 23) AS fecha,
                    TRIM(UPPER(dp.NombreProducto)) AS producto,
                    TRIM(UPPER(dr.Provincia)) AS provincia,
                    TRIM(UPPER(dr.Canton)) AS canton,
                    TRIM(UPPER(dr.Zona)) AS distrito,
                    f.Precio AS precio
                FROM dbo.FactPreciosCanasta f
                INNER JOIN dbo.DimFecha df
                    ON f.FechaID = df.FechaID
                INNER JOIN dbo.DimProducto dp
                    ON f.ProductoID = dp.ProductoID
                INNER JOIN dbo.DimRegion dr
                    ON f.RegionID = dr.RegionID
                WHERE dp.Categoria <> 'Combustibles'
                """,
            )
            self._actualizar_estadisticas("canasta", dw=perfil_canasta_dw.filas)

            perfil_clima_dw = self._validadores["clima"].registrar_sql(
                "dw",
                self.db,
                """
                SELECT
                    TRIM(UPPER(z.NombreZona)) AS zona,
                    CAST(z.Latitud AS DECIMAL(9,6)) AS latitud,
                    CAST(z.Longitud AS DECIMAL(9,6)) AS longitud,
                    c.FechaID AS fecha_id,
                    c.TempMax AS temp_max,
                    c.TempMin AS temp_min,
                    c.Precipitacion AS precipitacion,
                    c.Humedad AS humedad,
                    c.RadiacionSolar AS radiacion_solar
                FROM dbo.FactClimaMensual c
                INNER JOIN dbo.DimZonaClimatica z
                    ON c.ZonaClimaticaID = z.ZonaClimaticaID
                """,
            )
            self._actualizar_estadisticas("clima", dw=perfil_clima_dw.filas)

            self._ejecutar_etapa("Auditoria del DW", self._auditar_dw_sql)
            print("Proceso finalizado exitosamente")
            self._imprimir_resumen_dominios()
            print(
                f"[ETL] Tiempo total del flujo real: "
                f"{formatear_duracion(time.perf_counter() - self._inicio_flujo)}"
            )
            return 0
        except Exception as exc:
            print(f"Error critico en el ETL: {exc}")
            print(
                f"[ETL] Tiempo acumulado antes del error: "
                f"{formatear_duracion(time.perf_counter() - self._inicio_flujo)}"
            )
            return 1

    def _obtener_clima(self) -> pd.DataFrame:
        guardar_historicos = self.parametros.es_historico or self.parametros.generar_historicos
        df_origen = self.extractor_clima.obtener(guardar_csv=guardar_historicos)
        df_origen_normalizado = self._normalizar_clima(df_origen)
        validar_columnas_obligatorias(
            df_origen_normalizado,
            (
                "zona",
                "latitud",
                "longitud",
                "fecha_id",
                "temp_max",
                "temp_min",
                "precipitacion",
                "humedad",
                "radiacion_solar",
            ),
            "clima/origen",
        )
        self._crear_validador_clima()
        self._validadores["clima"].registrar_dataframe("origen", df_origen_normalizado)
        self._actualizar_estadisticas("clima", leidas=len(df_origen_normalizado))

        if guardar_historicos:
            df_csv = self._normalizar_clima(
                pd.read_csv(self.raw_data_dir / "clima_historico.csv", encoding="utf-8-sig")
            )
            validar_columnas_obligatorias(
                df_csv,
                (
                    "zona",
                    "latitud",
                    "longitud",
                    "fecha_id",
                    "temp_max",
                    "temp_min",
                    "precipitacion",
                    "humedad",
                    "radiacion_solar",
                ),
                "clima/csv",
            )
            self._validadores["clima"].registrar_dataframe("csv", df_csv)
            self._actualizar_estadisticas("clima", csv=len(df_csv))

        df_transformado = self.transformador_clima.transformar(df_origen)
        df_transformado_normalizado = self._normalizar_clima(df_transformado)
        if df_transformado.empty:
            raise RuntimeError("No hay datos climaticos utilizables para poblar staging o DW.")
        validar_columnas_obligatorias(
            df_transformado_normalizado,
            (
                "zona",
                "latitud",
                "longitud",
                "fecha_id",
                "temp_max",
                "temp_min",
                "precipitacion",
                "humedad",
                "radiacion_solar",
            ),
            "clima/transformado",
        )
        self._validadores["clima"].registrar_dataframe("transformado", df_transformado_normalizado)
        self._actualizar_estadisticas("clima", transformadas=len(df_transformado_normalizado))
        return df_transformado

    def _trazar_tipo_cambio(self, registros: list, registrar_csv: bool) -> None:
        dataframe = pd.DataFrame(
            [
                {
                    "fecha": registro.fecha.strftime("%Y-%m-%d"),
                    "compra": registro.compra,
                    "venta": registro.venta,
                }
                for registro in registros
            ]
        )
        validar_columnas_obligatorias(
            dataframe,
            ("fecha", "compra", "venta"),
            "tipo_cambio/origen",
        )
        validador = ValidadorTrazabilidad(
            "tipo_cambio",
            ("fecha",),
            ("compra", "venta"),
        )
        validador.registrar_dataframe("origen", dataframe)
        self._actualizar_estadisticas("tipo_cambio", leidas=len(dataframe))
        if registrar_csv:
            df_csv = self._normalizar_tipo_cambio_csv(
                pd.read_csv(self.raw_data_dir / "tipo_cambio_historico.csv", encoding="utf-8-sig")
            )
            if not self.parametros.es_historico:
                df_csv = self._filtrar_tipo_cambio_csv_por_alcance(df_csv, dataframe)
            validar_columnas_obligatorias(
                df_csv,
                ("fecha", "compra", "venta"),
                "tipo_cambio/csv",
            )
            validador.registrar_dataframe("csv", df_csv)
            self._actualizar_estadisticas("tipo_cambio", csv=len(df_csv))
        self._validadores["tipo_cambio"] = validador

    def _depurar_registros_combustible(self, registros: list[dict]) -> list[dict]:
        dataframe = pd.DataFrame(registros)
        validar_columnas_obligatorias(dataframe, ("producto",), "combustibles/origen")
        if "fechaPublicacion" not in dataframe.columns:
            raise ValueError("combustibles/origen: falta la columna fechaPublicacion.")

        registros_utilizables = [
            registro for registro in registros if es_registro_combustible_utilizable(registro)
        ]
        descartadas = len(registros) - len(registros_utilizables)
        self._actualizar_estadisticas(
            "combustibles",
            leidas=len(registros),
            descartadas=descartadas,
        )
        if descartadas > 0:
            print(
                f"[TRACE-COMBUSTIBLES] origen: {descartadas} filas se descartaron por datos "
                f"incompletos antes de CSV, staging y DW."
            )
        return registros_utilizables

    def _trazar_combustibles(
        self,
        productos: list,
        precios: list,
        registrar_csv: bool,
    ) -> None:
        dataframe_precios = pd.DataFrame(
            [
                {
                    "fecha": str(precio.fecha_raw)[:10],
                    "producto": clasificar_producto_combustible(precio.nombre_producto_raw)[
                        "nombre_canonico"
                    ],
                    "precio": precio.precio,
                }
                for precio in precios
            ]
        )
        validar_columnas_obligatorias(
            dataframe_precios,
            ("fecha", "producto", "precio"),
            "combustibles/transformado",
        )

        validador = ValidadorTrazabilidad(
            "combustibles",
            ("fecha", "producto"),
            ("precio",),
        )
        validador.registrar_dataframe("transformado", dataframe_precios)
        self._actualizar_estadisticas("combustibles", transformadas=len(dataframe_precios))

        if registrar_csv:
            df_csv = self._normalizar_combustible_csv(
                pd.read_csv(self.raw_data_dir / "combustible_historico.csv", encoding="utf-8-sig")
            )
            validar_columnas_obligatorias(
                df_csv,
                ("fecha", "producto", "precio"),
                "combustibles/csv",
            )
            validador.registrar_dataframe("csv", df_csv)
            self._actualizar_estadisticas("combustibles", csv=len(df_csv))
        self._validadores["combustible_precios"] = validador

        dataframe_productos = pd.DataFrame(
            [
                {
                    "producto": producto.nombre_normalizado.strip().upper(),
                    "categoria": producto.categoria,
                    "subcategoria": producto.subcategoria,
                    "unidad_medida": producto.unidad_medida,
                }
                for producto in productos
            ]
        )
        validar_columnas_obligatorias(
            dataframe_productos,
            ("producto", "categoria", "subcategoria", "unidad_medida"),
            "combustibles/productos_transformados",
        )

    def _trazar_canasta(self, ruta_canasta: Path, df_canasta: pd.DataFrame) -> None:
        df_csv = pd.read_csv(ruta_canasta, encoding="utf-8-sig")
        df_csv_normalizado = self._normalizar_canasta(df_csv)
        validar_columnas_obligatorias(
            df_csv_normalizado,
            ("fecha", "producto", "provincia", "canton", "distrito", "precio"),
            "canasta/csv",
        )
        df_transformado = self._normalizar_canasta(df_canasta)
        validar_columnas_obligatorias(
            df_transformado,
            ("fecha", "producto", "provincia", "canton", "distrito", "precio"),
            "canasta/transformado",
        )

        validador = ValidadorTrazabilidad(
            "canasta",
            ("fecha", "producto", "provincia", "canton", "distrito"),
            ("precio",),
        )
        validador.registrar_dataframe("csv", df_csv_normalizado)
        validador.registrar_dataframe("transformado", df_transformado)
        self._validadores["canasta"] = validador
        self._actualizar_estadisticas("canasta", leidas=len(df_csv_normalizado), csv=len(df_csv_normalizado), transformadas=len(df_transformado))

    def _crear_validador_clima(self) -> None:
        if "clima" in self._validadores:
            return
        self._validadores["clima"] = ValidadorTrazabilidad(
            "clima",
            ("zona", "latitud", "longitud", "fecha_id"),
            ("temp_max", "temp_min", "precipitacion", "humedad", "radiacion_solar"),
        )

    def _auditar_staging_sql(self) -> None:
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.StagingFecha",
            ("FechaID", "Fecha", "Dia", "Mes", "NombreMes", "Año", "Trimestre"),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.StagingTipoCambio",
            (
                "Fecha",
                "FechaID",
                "MonedaBaseID",
                "MonedaReferenciaID",
                "FuenteID",
                "TipoCambioCompra",
                "TipoCambioVenta",
                "TipoCambioPromedio",
            ),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.StagingPrecioGasolina",
            ("FechaRaw", "NombreProductoRaw", "Precio", "FuenteID"),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.StagingProducto",
            (
                "NombreRaw",
                "NombreNormalizado",
                "Categoria",
                "SubCategoria",
                "UnidadMedida",
                "FuenteID",
                "EsImportado",
                "PrecioBaseReferencia",
                "FactorCanasta",
            ),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.StagingHistoricoCanasta",
            ("Fecha", "NombreProductoRaw", "Provincia", "Canton", "Distrito", "PrecioColones", "FuenteID"),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.StagingZonaClimatica",
            ("NombreZona", "Latitud", "Longitud", "FuenteID"),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.StagingClimaMensual",
            (
                "Fecha",
                "FechaID",
                "NombreZona",
                "Latitud",
                "Longitud",
                "TempMax",
                "TempMin",
                "Precipitacion",
                "Humedad",
                "RadiacionSolar",
                "FuenteID",
            ),
        )

    def _auditar_dw_sql(self) -> None:
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.DimFecha",
            ("FechaID", "Fecha", "Dia", "Mes", "NombreMes", "Año", "Trimestre"),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.DimFuenteDatos",
            ("FuenteID", "NombreFuente", "Descripcion"),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.DimMoneda",
            ("MonedaID", "NombreMoneda", "CodigoMoneda"),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.DimProducto",
            (
                "ProductoID",
                "NombreProducto",
                "Categoria",
                "UnidadMedida",
                "EsImportado",
                "PrecioBaseReferencia",
                "FactorCanasta",
            ),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.DimRegion",
            ("RegionID", "Provincia", "Canton", "Zona"),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.DimZonaClimatica",
            ("ZonaClimaticaID", "NombreZona", "Latitud", "Longitud"),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.FactTipoCambio",
            ("FactTipoCambioID", "FechaID", "MonedaBaseID", "MonedaReferenciaID", "FuenteID", "TipoCambioCompra", "TipoCambioVenta"),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.FactPrecioCombustible",
            ("FactPrecioCombustibleID", "FechaID", "ProductoID", "MonedaID", "FuenteID", "Precio"),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.FactPreciosCanasta",
            ("FactPrecioID", "FechaID", "ProductoID", "RegionID", "MonedaID", "FuenteID", "Precio", "IPC", "CostoCanastaTotal"),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.FactClimaMensual",
            ("FactClimaMensualID", "FechaID", "ZonaClimaticaID", "FuenteID", "TempMax", "TempMin", "Precipitacion", "Humedad", "RadiacionSolar"),
        )

    def _ejecutar_etapa(self, nombre: str, funcion):
        inicio_etapa = time.perf_counter()
        resultado = funcion()
        duracion = time.perf_counter() - inicio_etapa
        acumulado = time.perf_counter() - self._inicio_flujo
        print(
            f"[ETL] {nombre}: {formatear_duracion(duracion)} | "
            f"Acumulado flujo real: {formatear_duracion(acumulado)}"
        )
        return resultado

    @staticmethod
    def _normalizar_tipo_cambio_csv(dataframe: pd.DataFrame) -> pd.DataFrame:
        df = dataframe.copy()
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.strftime("%Y-%m-%d")
        df["compra"] = pd.to_numeric(df["compra"], errors="coerce")
        df["venta"] = pd.to_numeric(df["venta"], errors="coerce")
        return df[["fecha", "compra", "venta"]].dropna(subset=["fecha"])

    @staticmethod
    def _filtrar_tipo_cambio_csv_por_alcance(
        dataframe_csv: pd.DataFrame,
        dataframe_actual: pd.DataFrame,
    ) -> pd.DataFrame:
        if dataframe_csv.empty or dataframe_actual.empty:
            return dataframe_csv
        fechas_actuales = set(dataframe_actual["fecha"].astype(str))
        return dataframe_csv[dataframe_csv["fecha"].astype(str).isin(fechas_actuales)].reset_index(
            drop=True
        )

    @staticmethod
    def _normalizar_combustible_csv(dataframe: pd.DataFrame) -> pd.DataFrame:
        df = dataframe.copy()
        df["fecha"] = df["fechaPublicacion"].astype(str).str[:10]
        df["producto"] = df["producto"].apply(
            lambda valor: (
                clasificar_producto_combustible(valor)["nombre_canonico"]
                if clasificar_producto_combustible(valor) is not None
                else None
            )
        )
        df["precio"] = pd.to_numeric(df["precioFinal"], errors="coerce")
        df = df.dropna(subset=["producto"])
        return df[["fecha", "producto", "precio"]].dropna(subset=["precio"])

    @staticmethod
    def _normalizar_canasta(dataframe: pd.DataFrame) -> pd.DataFrame:
        df = dataframe.copy()
        df["fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.strftime("%Y-%m-%d")
        df["producto"] = df["NombreProducto"].astype(str).str.upper().str.strip()
        df["provincia"] = df["Provincia"].astype(str).str.upper().str.strip()
        df["canton"] = df["Canton"].astype(str).str.upper().str.strip()
        df["distrito"] = df["Distrito"].astype(str).str.upper().str.strip()
        df["precio"] = pd.to_numeric(df["PrecioColones"], errors="coerce")
        return df[["fecha", "producto", "provincia", "canton", "distrito", "precio"]]

    @staticmethod
    def _normalizar_clima(dataframe: pd.DataFrame) -> pd.DataFrame:
        df = dataframe.rename(
            columns={
                "Zona": "zona",
                "Latitud": "latitud",
                "Longitud": "longitud",
                "AÃ±o": "anio",
                "AÃƒÂ±o": "anio",
                "Anio": "anio",
                "Mes": "mes",
                "FechaID": "fecha_id",
                "Temp_Max": "temp_max",
                "Temp_Min": "temp_min",
                "Precipitacion": "precipitacion",
                "Humedad": "humedad",
                "RadiacionSolar": "radiacion_solar",
            }
        ).copy()
        df["zona"] = df["zona"].astype(str).str.upper().str.strip()
        columnas_numericas = (
            "latitud",
            "longitud",
            "anio",
            "mes",
            "fecha_id",
            "temp_max",
            "temp_min",
            "precipitacion",
            "humedad",
            "radiacion_solar",
        )
        for columna in columnas_numericas:
            if columna in df.columns:
                df[columna] = pd.to_numeric(df[columna], errors="coerce")
            else:
                df[columna] = pd.Series(pd.NA, index=df.index, dtype="Float64")
        if "fecha_id" not in df.columns or df["fecha_id"].isna().any():
            df["fecha_id"] = pd.to_numeric(
                df["anio"].astype("Int64").astype(str)
                + df["mes"].astype("Int64").astype(str).str.zfill(2)
                + "01",
                errors="coerce",
            )
        df["latitud"] = df["latitud"].round(6)
        df["longitud"] = df["longitud"].round(6)
        return df[
            [
                "zona",
                "latitud",
                "longitud",
                "fecha_id",
                "temp_max",
                "temp_min",
                "precipitacion",
                "humedad",
                "radiacion_solar",
            ]
        ]

    def _actualizar_estadisticas(self, dominio: str, **valores: int) -> None:
        bucket = self._estadisticas.setdefault(dominio, {})
        for clave, valor in valores.items():
            bucket[clave] = int(valor)

    def _imprimir_resumen_dominios(self) -> None:
        if not self._estadisticas:
            return
        print("=" * 50)
        print("RESUMEN DE DOMINIOS")
        print("=" * 50)
        for dominio, datos in self._estadisticas.items():
            resumen = ", ".join(f"{clave}={valor}" for clave, valor in datos.items())
            print(f"[RESUMEN-{dominio.upper()}] {resumen}")
