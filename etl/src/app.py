from __future__ import annotations

from pathlib import Path
import time

import pandas as pd

from admin_db_conn.config import ParametrosETL
from admin_db_conn.db import SqlServerDB
from dw_manager import CoordinadorDW
from etl_cba.extract import ExtractorCBAOficial
from etl_cba.load import CargadorCBA
from etl_cba.transform import TransformadorCBA
from etl_cba.validation import ValidadorCBAOficial
from etl_clima.extract import ExtractorClimaNASA
from etl_clima.load import CargadorClima
from etl_clima.transform import TransformadorClima
from etl_combustible.combustibles import (
    clasificar_producto_combustible,
    es_registro_combustible_utilizable,
)
from etl_combustible.extract import ExtractorCombustible
from etl_combustible.load import CargadorCombustible
from etl_combustible.transform import TransformadorCombustible
from etl_dolar.extract import ExtractorTipoCambio
from etl_dolar.load import CargadorDolar
from runtime import formatear_duracion
from trazabilidad import (
    ValidadorTrazabilidad,
    auditar_tabla_sql_no_nulos,
    validar_columnas_obligatorias,
)


class ETLApp:
    def __init__(self, parametros: ParametrosETL, base_dir: Path) -> None:
        self.parametros = parametros
        self.base_dir = base_dir
        self.raw_data_dir = base_dir / "etl" / "data" / "raw"
        self.raw_cba_dir = self.raw_data_dir / "cba"
        self.db = SqlServerDB(parametros)
        self.coordinador_dw = CoordinadorDW(self.db)
        self.extractor_tipo_cambio = ExtractorTipoCambio(
            self.raw_data_dir / "tipo_cambio_historico.csv"
        )
        self.cargador_dolar = CargadorDolar(self.db)
        self.extractor_combustible = ExtractorCombustible(
            self.raw_data_dir / "combustible_historico.csv"
        )
        self.transformador_combustible = TransformadorCombustible()
        self.cargador_combustible = CargadorCombustible(self.db)
        self.extractor_cba = ExtractorCBAOficial(self.raw_cba_dir)
        self.transformador_cba = TransformadorCBA()
        self.validador_cba_oficial = ValidadorCBAOficial()
        self.cargador_cba = CargadorCBA(self.db)
        self.extractor_clima = ExtractorClimaNASA(
            ruta_respaldo_csv=self.raw_data_dir / "clima_historico.csv"
        )
        self.transformador_clima = TransformadorClima()
        self.cargador_clima = CargadorClima(
            ruta_salida_csv=self.raw_data_dir / "clima_historico.csv",
            db=self.db,
        )
        self._inicio_flujo = 0.0
        self._validadores: dict[str, ValidadorTrazabilidad] = {}
        self._estadisticas: dict[str, dict[str, int]] = {}

    def ejecutar(self) -> int:
        print("=" * 50)
        print("ETL - DOLAR, COMBUSTIBLES, CBA OFICIAL Y CLIMA")
        print("=" * 50)
        self._inicio_flujo = time.perf_counter()
        guardar_historicos = self.parametros.es_historico or self.parametros.generar_historicos

        try:
            self._ejecutar_etapa("Limpieza de staging", self.coordinador_dw.limpiar_staging)

            if self.parametros.es_historico:
                print("Modo historico")
                registros_tc = self._ejecutar_etapa(
                    "Extraccion dolar historico",
                    lambda: self.extractor_tipo_cambio.obtener_historico(
                        guardar_csv=guardar_historicos,
                        sobrescribir_csv=True,
                    ),
                )
            else:
                print("Modo direct-insert")
                registros_tc = self._ejecutar_etapa(
                    "Extraccion dolar diario",
                    lambda: [
                        self.extractor_tipo_cambio.obtener_diario(
                            guardar_csv=guardar_historicos,
                            sobrescribir_csv=False,
                        )
                    ],
                )

            self._trazar_tipo_cambio(registros_tc, registrar_csv=guardar_historicos)
            self._ejecutar_etapa(
                "Carga staging dolar",
                lambda: self.cargador_dolar.cargar_staging(registros_tc),
            )
            perfil_tc_staging = self._validadores["dolar"].registrar_sql(
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
            self._actualizar_estadisticas("dolar", staging=perfil_tc_staging.filas)

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
                lambda: self.cargador_combustible.cargar_staging(productos, precios),
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
            self._actualizar_estadisticas("combustible", staging=perfil_comb_staging.filas)

            resultado_cba = self._ejecutar_etapa("Extraccion CBA oficial", self.extractor_cba.extraer)
            df_cba = self._ejecutar_etapa(
                "Transformacion CBA oficial",
                lambda: self.transformador_cba.transformar_detalle(resultado_cba.detalle),
            )
            df_cba_control = self._ejecutar_etapa(
                "Transformacion consolidado CBA",
                lambda: self.transformador_cba.transformar_control(resultado_cba.consolidado),
            )
            self._ejecutar_etapa(
                "Validacion CBA oficial",
                lambda: self.validador_cba_oficial.validar_reconciliacion(df_cba, df_cba_control),
            )
            self._trazar_cba(df_cba, df_cba_control)
            self._ejecutar_etapa(
                "Carga staging CBA oficial",
                lambda: self.cargador_cba.cargar_staging(df_cba),
            )
            perfil_cba_staging = self._validadores["cba"].registrar_sql(
                "staging",
                self.db,
                """
                SELECT
                    FechaID AS fecha_id,
                    TRIM(UPPER(Zona)) AS zona,
                    TRIM(UPPER(CategoriaNombre)) AS categoria,
                    CostoPerCapita AS costo_per_capita
                FROM dbo.StagingInec
                """,
            )
            self._actualizar_estadisticas("cba", staging=perfil_cba_staging.filas)

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
            self._ejecutar_etapa("Asegurar catalogos base", self.coordinador_dw.asegurar_catalogos_base)
            self._ejecutar_etapa(
                "Carga final del DW mediante procedimientos",
                self.coordinador_dw.ejecutar_transformaciones_dw,
            )

            perfil_tc_dw = self._validadores["dolar"].registrar_sql(
                "dw",
                self.db,
                """
                SELECT
                    CONVERT(VARCHAR(10), d.Fecha, 23) AS fecha,
                    f.TipoCambioCompra AS compra,
                    f.TipoCambioVenta AS venta
                FROM dbo.FactTipoCambio f
                INNER JOIN dbo.DimFecha d ON f.FechaID = d.FechaID
                """,
            )
            self._actualizar_estadisticas("dolar", dw=perfil_tc_dw.filas)

            perfil_comb_dw = self._validadores["combustible_precios"].registrar_sql(
                "dw",
                self.db,
                """
                SELECT
                    CONVERT(VARCHAR(10), d.Fecha, 23) AS fecha,
                    TRIM(UPPER(p.NombreProducto)) AS producto,
                    f.Precio AS precio
                FROM dbo.FactPrecioCombustible f
                INNER JOIN dbo.DimFecha d ON f.FechaID = d.FechaID
                INNER JOIN dbo.DimProducto p ON f.ProductoID = p.ProductoID
                WHERE p.Categoria = 'Combustibles'
                """,
            )
            self._actualizar_estadisticas("combustible", dw=perfil_comb_dw.filas)

            perfil_cba_dw = self._validadores["cba"].registrar_sql(
                "dw",
                self.db,
                """
                SELECT
                    f.FechaID AS fecha_id,
                    TRIM(UPPER(z.NombreZona)) AS zona,
                    TRIM(UPPER(c.NombreCategoria)) AS categoria,
                    f.CostoPerCapita AS costo_per_capita
                FROM dbo.FactCanastaInecOficial f
                INNER JOIN dbo.DimZonaCBA z ON f.ZonaCBAID = z.ZonaCBAID
                INNER JOIN dbo.DimCategoriaCBA c ON f.CategoriaCBAID = c.CategoriaCBAID
                """,
            )
            self._actualizar_estadisticas("cba", dw=perfil_cba_dw.filas)

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
                INNER JOIN dbo.DimZonaClimatica z ON c.ZonaClimaticaID = z.ZonaClimaticaID
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
        validar_columnas_obligatorias(dataframe, ("fecha", "compra", "venta"), "dolar/origen")
        validador = ValidadorTrazabilidad("dolar", ("fecha",), ("compra", "venta"))
        validador.registrar_dataframe("origen", dataframe)
        self._actualizar_estadisticas("dolar", leidas=len(dataframe))
        if registrar_csv:
            df_csv = self._normalizar_tipo_cambio_csv(
                pd.read_csv(self.raw_data_dir / "tipo_cambio_historico.csv", encoding="utf-8-sig")
            )
            if not self.parametros.es_historico:
                df_csv = self._filtrar_tipo_cambio_csv_por_alcance(df_csv, dataframe)
            validar_columnas_obligatorias(df_csv, ("fecha", "compra", "venta"), "dolar/csv")
            validador.registrar_dataframe("csv", df_csv)
            self._actualizar_estadisticas("dolar", csv=len(df_csv))
        self._validadores["dolar"] = validador

    def _depurar_registros_combustible(self, registros: list[dict]) -> list[dict]:
        dataframe = pd.DataFrame(registros)
        validar_columnas_obligatorias(dataframe, ("producto",), "combustible/origen")
        if "fechaPublicacion" not in dataframe.columns:
            raise ValueError("combustible/origen: falta la columna fechaPublicacion.")

        registros_utilizables = [
            registro for registro in registros if es_registro_combustible_utilizable(registro)
        ]
        descartadas = len(registros) - len(registros_utilizables)
        self._actualizar_estadisticas(
            "combustible",
            leidas=len(registros),
            descartadas=descartadas,
        )
        if descartadas > 0:
            print(
                f"[TRACE-COMBUSTIBLE] origen: {descartadas} filas se descartaron por datos "
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
            "combustible/transformado",
        )

        validador = ValidadorTrazabilidad(
            "combustible",
            ("fecha", "producto"),
            ("precio",),
        )
        validador.registrar_dataframe("transformado", dataframe_precios)
        self._actualizar_estadisticas("combustible", transformadas=len(dataframe_precios))

        if registrar_csv:
            df_csv = self._normalizar_combustible_csv(
                pd.read_csv(self.raw_data_dir / "combustible_historico.csv", encoding="utf-8-sig")
            )
            validar_columnas_obligatorias(
                df_csv,
                ("fecha", "producto", "precio"),
                "combustible/csv",
            )
            validador.registrar_dataframe("csv", df_csv)
            self._actualizar_estadisticas("combustible", csv=len(df_csv))
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
            "combustible/productos_transformados",
        )

    def _trazar_cba(self, df_cba: pd.DataFrame, df_cba_control: pd.DataFrame) -> None:
        df_transformado = self._normalizar_cba(df_cba)
        validar_columnas_obligatorias(
            df_transformado,
            ("fecha_id", "zona", "categoria", "costo_per_capita"),
            "cba/transformado",
        )
        validar_columnas_obligatorias(
            df_cba_control,
            ("FechaID", "Zona", "CostoPerCapitaControl"),
            "cba/control",
        )
        validador = ValidadorTrazabilidad(
            "cba",
            ("fecha_id", "zona", "categoria"),
            ("costo_per_capita",),
        )
        validador.registrar_dataframe("transformado", df_transformado)
        self._validadores["cba"] = validador
        self._actualizar_estadisticas(
            "cba",
            leidas=len(df_transformado),
            control=len(df_cba_control),
            transformadas=len(df_transformado),
        )

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
            ("FechaID", "Fecha", "Dia", "Mes", "NombreMes", "Anio", "Trimestre"),
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
            "dbo.StagingInec",
            (
                "Fecha",
                "FechaID",
                "Zona",
                "CategoriaNombre",
                "PeriodoTextoOriginal",
                "CostoPerCapita",
                "ArchivoOrigen",
                "FuenteID",
            ),
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
            ("FechaID", "Fecha", "Dia", "Mes", "NombreMes", "Anio", "Trimestre"),
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
                "NombreRaw",
                "NombreProducto",
                "Categoria",
                "SubCategoria",
                "FuenteID",
                "UnidadMedida",
                "EsImportado",
                "PrecioBaseReferencia",
                "FactorCanasta",
            ),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.DimZonaCBA",
            ("ZonaCBAID", "NombreZona", "FuenteID"),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.DimCategoriaCBA",
            ("CategoriaCBAID", "NombreCategoria", "FuenteID"),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.DimZonaClimatica",
            ("ZonaClimaticaID", "NombreZona", "Latitud", "Longitud", "FuenteID"),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.FactTipoCambio",
            (
                "FactTipoCambioID",
                "FechaID",
                "MonedaBaseID",
                "MonedaReferenciaID",
                "FuenteID",
                "TipoCambioCompra",
                "TipoCambioVenta",
            ),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.FactPrecioCombustible",
            ("FactPrecioCombustibleID", "FechaID", "ProductoID", "MonedaID", "FuenteID", "Precio"),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.FactCanastaInecOficial",
            (
                "CBAOficialKey",
                "FechaID",
                "ZonaCBAID",
                "CategoriaCBAID",
                "Zona",
                "CategoriaNombre",
                "PeriodoTextoOriginal",
                "FuenteID",
                "CostoPerCapita",
            ),
        )
        auditar_tabla_sql_no_nulos(
            self.db,
            "dbo.FactClimaMensual",
            (
                "FactClimaMensualID",
                "FechaID",
                "ZonaClimaticaID",
                "FuenteID",
                "TempMax",
                "TempMin",
                "Precipitacion",
                "Humedad",
                "RadiacionSolar",
            ),
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
    def _normalizar_cba(dataframe: pd.DataFrame) -> pd.DataFrame:
        df = dataframe.copy()
        df["fecha_id"] = pd.to_numeric(df["FechaID"], errors="coerce")
        df["zona"] = df["Zona"].astype(str).str.upper().str.strip()
        df["categoria"] = df["CategoriaNombre"].astype(str).str.upper().str.strip()
        df["costo_per_capita"] = pd.to_numeric(df["CostoPerCapita"], errors="coerce")
        return df[["fecha_id", "zona", "categoria", "costo_per_capita"]]

    @staticmethod
    def _normalizar_clima(dataframe: pd.DataFrame) -> pd.DataFrame:
        df = dataframe.rename(
            columns={
                "Zona": "zona",
                "Latitud": "latitud",
                "Longitud": "longitud",
                "AÃƒÂ±o": "anio",
                "AÃƒÆ’Ã‚Â±o": "anio",
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
