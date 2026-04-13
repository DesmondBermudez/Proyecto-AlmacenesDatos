from __future__ import annotations

from pathlib import Path
from time import perf_counter
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from admin_db_conn.db import SqlServerDB
from modelo_predictivo_cba.models import (
    ConfiguracionModeloCBA,
    ResultadoPipelineModeloCBA,
    ResultadoPrediccionModeloCBA,
    ResultadoValidacionVistasCBA,
    ResumenEntrenamientoModeloCBA,
)
from modelo_predictivo_cba.repository import RepositorioModeloCBA
from modelo_predictivo_cba.simple_model import ModeloLinealSimpleCBA


class ServicioModeloCBA:
    def __init__(
        self,
        db: SqlServerDB,
        configuracion: ConfiguracionModeloCBA | None = None,
    ) -> None:
        self.configuracion = configuracion or ConfiguracionModeloCBA()
        self.repositorio = RepositorioModeloCBA(db=db, configuracion=self.configuracion)

    def entrenar(self, ruta_modelo: Path | None = None) -> ResumenEntrenamientoModeloCBA:
        self.validar_vistas()
        dataframe = self.repositorio.cargar_entrenamiento()
        train_df, test_df = self._partir_dataframe_temporal(dataframe)

        metricas_algoritmos: list[dict[str, object]] = []
        comparacion_validacion = test_df[
            ["FechaMes", "Anio", "Mes", "ZonaCBAID", "NombreZona", self.configuracion.columna_objetivo]
        ].copy()

        tiempo_total = 0.0
        rutas_modelos: dict[str, Path] = {}

        for algoritmo in self.configuracion.algoritmos_candidatos:
            inicio = perf_counter()
            if not test_df.empty:
                validacion_algoritmo = self._crear_validacion_detallada(
                    train_df=train_df,
                    test_df=test_df,
                    algoritmo=algoritmo,
                )
                metricas = self._resumir_metricas(validacion_algoritmo, algoritmo)
                metricas["tiempo_validacion_segundos"] = perf_counter() - inicio
                metricas_algoritmos.append(metricas)
                comparacion_validacion = comparacion_validacion.merge(
                    validacion_algoritmo,
                    on=["FechaMes", "Anio", "Mes", "ZonaCBAID", "NombreZona", self.configuracion.columna_objetivo],
                    how="left",
                )
            else:
                metricas_algoritmos.append(
                    {
                        "algoritmo": algoritmo,
                        "precision_pct": None,
                        "precision_zona_min_pct": None,
                        "precision_zona_max_pct": None,
                        "mae": None,
                        "rmse": None,
                        "r2": None,
                        "tiempo_validacion_segundos": 0.0,
                    }
                )

            inicio_entrenamiento = perf_counter()
            modelo = ModeloLinealSimpleCBA(self.configuracion, algoritmo=algoritmo).fit(dataframe)
            modelo.metricas_algoritmos = metricas_algoritmos
            tiempo_entrenamiento = perf_counter() - inicio_entrenamiento
            tiempo_total += tiempo_entrenamiento

            ruta_modelo_algoritmo = self._ruta_modelo_algoritmo(
                ruta_modelo or self.configuracion.ruta_modelo,
                algoritmo,
            )
            rutas_modelos[algoritmo] = modelo.guardar(ruta_modelo_algoritmo)

            for item in metricas_algoritmos:
                if item["algoritmo"] == algoritmo:
                    item["tiempo_entrenamiento_segundos"] = tiempo_entrenamiento
                    break

        if metricas_algoritmos:
            precision_mejor = max(
                float(item["precision_pct"])
                for item in metricas_algoritmos
                if item["precision_pct"] is not None
            )
            if precision_mejor < self.configuracion.precision_minima_pct:
                raise ValueError(
                    "La mejor precision validada del modelo CBA fue "
                    f"{precision_mejor:.2f}% y no alcanza el minimo requerido "
                    f"de {self.configuracion.precision_minima_pct:.2f}%."
                )

        ruta_validacion: Path | None = None
        if not test_df.empty:
            ruta_validacion = self.configuracion.ruta_validacion
            ruta_validacion.parent.mkdir(parents=True, exist_ok=True)
            comparacion_validacion.to_csv(ruta_validacion, index=False, encoding="utf-8-sig")

        return ResumenEntrenamientoModeloCBA(
            filas_entrenamiento=len(train_df) if not test_df.empty else len(dataframe),
            filas_validacion=len(test_df),
            precision_minima_pct=self.configuracion.precision_minima_pct,
            tiempo_total_entrenamiento_segundos=tiempo_total,
            metricas_algoritmos=metricas_algoritmos,
            rutas_modelos=rutas_modelos,
            ruta_validacion=ruta_validacion,
        )

    def predecir(
        self,
        ruta_modelo: Path | None = None,
        ruta_predicciones: Path | None = None,
    ) -> ResultadoPrediccionModeloCBA:
        self.validar_vistas()
        entrenamiento = self.repositorio.cargar_entrenamiento()
        futuro = self.repositorio.cargar_prediccion()
        salida = futuro[
            [
                "FechaMes",
                "Anio",
                "Mes",
                "Trimestre",
                "ZonaCBAID",
                "NombreZona",
                "CantidadCategorias",
                "TipoCambioPromedioMensual",
                "PrecioCombustiblePromedioMensual",
                "TempMaxProm",
                "TempMinProm",
                "PrecipitacionProm",
                "HumedadProm",
                "RadiacionSolarProm",
                "FlagFinAnio",
            ]
        ].copy()

        algoritmos_utilizados: list[str] = []
        for algoritmo in self.configuracion.algoritmos_candidatos:
            modelo = ModeloLinealSimpleCBA.cargar(
                self._ruta_modelo_algoritmo(
                    ruta_modelo or self.configuracion.ruta_modelo,
                    algoritmo,
                ),
                configuracion=self.configuracion,
            )
            forecast = self._generar_forecast_recursivo(modelo, entrenamiento, futuro)
            nombre_columna = f"PrediccionCBA_{self._nombre_columna_algoritmo(algoritmo)}"
            salida[nombre_columna] = forecast["PrediccionCBA_TotalMensual"].to_numpy(dtype=float)
            algoritmos_utilizados.append(algoritmo)

        ruta_destino = ruta_predicciones or self.configuracion.ruta_predicciones
        ruta_destino.parent.mkdir(parents=True, exist_ok=True)
        salida.to_csv(ruta_destino, index=False, encoding="utf-8-sig")
        return ResultadoPrediccionModeloCBA(
            filas_generadas=len(salida),
            ruta_predicciones=ruta_destino,
            algoritmos_utilizados=algoritmos_utilizados,
            fecha_inicio_prediccion=str(pd.to_datetime(salida["FechaMes"]).min().date()),
            fecha_fin_prediccion=str(pd.to_datetime(salida["FechaMes"]).max().date()),
        )

    def comparar_cba_con_fuente_xlsx(self, ruta_salida: Path | None = None) -> Path:
        from etl_cba.extract import ExtractorCBAOficial
        from etl_cba.transform import TransformadorCBA

        extractor = ExtractorCBAOficial(Path("etl") / "data" / "raw" / "cba")
        transformador = TransformadorCBA()
        resultado = extractor.extraer()
        consolidado = transformador.transformar_control(resultado.consolidado)

        with self.repositorio.db.connection() as conn:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="pandas only supports SQLAlchemy connectable",
                    category=UserWarning,
                )
                dw = pd.read_sql(
                    """
                    SELECT
                        DATEFROMPARTS(f.Anio, f.Mes, 1) AS FechaMes,
                        c.FechaID,
                        UPPER(LTRIM(RTRIM(z.NombreZona))) AS Zona,
                        c.CostoPerCapita AS CBA_DW
                    FROM dbo.FactCanastaInecOficial c
                    INNER JOIN dbo.DimFecha f
                        ON f.FechaID = c.FechaID
                    INNER JOIN dbo.DimZonaCBA z
                        ON z.ZonaCBAID = c.ZonaCBAID
                    INNER JOIN dbo.DimCategoriaCBA dc
                        ON dc.CategoriaCBAID = c.CategoriaCBAID
                    WHERE UPPER(LTRIM(RTRIM(z.NombreZona))) IN ('NACIONAL', 'RURAL', 'URBANO')
                      AND TRIM(UPPER(dc.NombreCategoria)) = 'CBA'
                    """,
                    conn,
                )

        consolidado["Zona"] = consolidado["Zona"].astype(str).str.upper().str.strip()
        comparacion = consolidado.merge(
            dw,
            on=["FechaID", "Zona"],
            how="outer",
        )
        comparacion["FechaMes"] = pd.to_datetime(
            comparacion["FechaMes"].fillna(pd.to_datetime(comparacion["Fecha"], errors="coerce")),
            errors="coerce",
        )
        comparacion["CBA_XLSX"] = pd.to_numeric(
            comparacion["CostoPerCapitaControl"],
            errors="coerce",
        )
        comparacion["CBA_DW"] = pd.to_numeric(comparacion["CBA_DW"], errors="coerce")
        comparacion["DiferenciaAbs"] = (comparacion["CBA_DW"] - comparacion["CBA_XLSX"]).abs()
        comparacion["DiferenciaPct"] = (
            comparacion["DiferenciaAbs"] / comparacion["CBA_XLSX"].abs().replace(0, np.nan)
        ) * 100.0
        comparacion = comparacion[
            [
                "FechaMes",
                "FechaID",
                "Zona",
                "CBA_XLSX",
                "CBA_DW",
                "DiferenciaAbs",
                "DiferenciaPct",
                "ArchivoOrigenControl",
            ]
        ].sort_values(by=["FechaMes", "Zona"]).reset_index(drop=True)

        ruta_destino = ruta_salida or Path("etl") / "data" / "processed" / "comparacion_cba_xlsx_vs_dw.csv"
        ruta_destino.parent.mkdir(parents=True, exist_ok=True)
        comparacion.to_csv(ruta_destino, index=False, encoding="utf-8-sig")
        return ruta_destino

    def validar_vistas(self) -> ResultadoValidacionVistasCBA:
        columnas_entrenamiento = self.repositorio.validar_vista_entrenamiento()
        columnas_prediccion = self.repositorio.validar_vista_prediccion()
        return ResultadoValidacionVistasCBA(
            vista_entrenamiento=self.configuracion.vista_entrenamiento,
            vista_prediccion=self.configuracion.vista_prediccion,
            columnas_entrenamiento=columnas_entrenamiento,
            columnas_prediccion=columnas_prediccion,
        )

    def pipeline(
        self,
        ruta_modelo: Path | None = None,
        ruta_predicciones: Path | None = None,
    ) -> ResultadoPipelineModeloCBA:
        validacion = self.validar_vistas()
        entrenamiento = self.entrenar(ruta_modelo=ruta_modelo)
        prediccion = self.predecir(
            ruta_modelo=ruta_modelo,
            ruta_predicciones=ruta_predicciones,
        )
        return ResultadoPipelineModeloCBA(
            validacion=validacion,
            entrenamiento=entrenamiento,
            prediccion=prediccion,
        )

    def _partir_dataframe_temporal(self, dataframe: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        if dataframe.empty:
            raise ValueError("La vista de entrenamiento no devolvio filas.")
        df = dataframe.copy()
        df[self.configuracion.columna_fecha] = pd.to_datetime(
            df[self.configuracion.columna_fecha],
            errors="coerce",
        )
        if df[self.configuracion.columna_fecha].isna().all():
            raise ValueError("La vista de entrenamiento no contiene fechas validas.")

        test_df = df[df["Anio"] == self.configuracion.anio_validacion_preferido].reset_index(drop=True)
        if not test_df.empty:
            train_df = df[df["Anio"] < self.configuracion.anio_validacion_preferido].reset_index(drop=True)
            if not train_df.empty:
                return train_df, test_df

        fechas = sorted(df[self.configuracion.columna_fecha].dropna().unique().tolist())
        if len(fechas) < 6:
            return df, df.iloc[0:0].copy()

        cantidad_test = max(1, int(len(fechas) * 0.2))
        fechas_test = set(fechas[-cantidad_test:])
        test_df = df[df[self.configuracion.columna_fecha].isin(fechas_test)].reset_index(drop=True)
        train_df = df[~df[self.configuracion.columna_fecha].isin(fechas_test)].reset_index(drop=True)
        if train_df.empty:
            return df, df.iloc[0:0].copy()
        return train_df, test_df

    def _crear_validacion_detallada(
        self,
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        algoritmo: str,
    ) -> pd.DataFrame:
        modelo = ModeloLinealSimpleCBA(self.configuracion, algoritmo=algoritmo).fit(train_df)
        salida = self._generar_forecast_recursivo(modelo, train_df, test_df)
        nombre_algoritmo = self._nombre_columna_algoritmo(algoritmo)
        objetivo = pd.to_numeric(test_df[self.configuracion.columna_objetivo], errors="raise")
        salida[f"PrediccionCBA_{nombre_algoritmo}"] = salida["PrediccionCBA_TotalMensual"]
        salida[f"ErrorAbs_{nombre_algoritmo}"] = (objetivo.to_numpy(dtype=float) - salida["PrediccionCBA_TotalMensual"]).astype(float)
        salida[f"ErrorAbs_{nombre_algoritmo}"] = salida[f"ErrorAbs_{nombre_algoritmo}"].abs()
        denominador = objetivo.abs().replace(0, np.nan)
        salida[f"ErrorPct_{nombre_algoritmo}"] = (
            salida[f"ErrorAbs_{nombre_algoritmo}"] / denominador
        ).fillna(0.0) * 100.0
        salida[f"PrecisionFilaPct_{nombre_algoritmo}"] = (
            100.0 - salida[f"ErrorPct_{nombre_algoritmo}"]
        ).clip(lower=0.0, upper=100.0)
        return salida[
            [
                "FechaMes",
                "Anio",
                "Mes",
                "ZonaCBAID",
                "NombreZona",
                self.configuracion.columna_objetivo,
                f"PrediccionCBA_{nombre_algoritmo}",
                f"ErrorAbs_{nombre_algoritmo}",
                f"ErrorPct_{nombre_algoritmo}",
                f"PrecisionFilaPct_{nombre_algoritmo}",
            ]
        ]

    def _resumir_metricas(
        self,
        validacion_algoritmo: pd.DataFrame,
        algoritmo: str,
    ) -> dict[str, object]:
        nombre_algoritmo = self._nombre_columna_algoritmo(algoritmo)
        real = pd.to_numeric(validacion_algoritmo[self.configuracion.columna_objetivo], errors="raise").to_numpy(dtype=float)
        pred = pd.to_numeric(validacion_algoritmo[f"PrediccionCBA_{nombre_algoritmo}"], errors="raise").to_numpy(dtype=float)
        precision_zona = validacion_algoritmo.groupby("ZonaCBAID")[f"PrecisionFilaPct_{nombre_algoritmo}"].mean()
        return {
            "algoritmo": algoritmo,
            "precision_pct": self._precision_desde_arrays(real, pred),
            "precision_zona_min_pct": float(precision_zona.min()),
            "precision_zona_max_pct": float(precision_zona.max()),
            "mae": float(mean_absolute_error(real, pred)),
            "rmse": float(np.sqrt(mean_squared_error(real, pred))),
            "r2": float(r2_score(real, pred)),
        }

    def _generar_forecast_recursivo(
        self,
        modelo: ModeloLinealSimpleCBA,
        entrenamiento: pd.DataFrame,
        futuro: pd.DataFrame,
    ) -> pd.DataFrame:
        if futuro.empty:
            raise ValueError("La vista de prediccion no devolvio filas para forecast.")

        historial_por_zona: dict[int, list[float]] = {}
        entrenamiento_ordenado = entrenamiento.sort_values(
            by=["ZonaCBAID", self.configuracion.columna_fecha]
        ).reset_index(drop=True)
        for zona_id, grupo in entrenamiento_ordenado.groupby("ZonaCBAID"):
            historial = (
                pd.to_numeric(grupo[self.configuracion.columna_objetivo], errors="raise")
                .astype(float)
                .tolist()
            )
            if len(historial) < max(3, len(self.configuracion.columnas_lags)):
                raise ValueError(
                    f"No hay suficiente historial para pronosticar la zona {zona_id}."
                )
            historial_por_zona[int(zona_id)] = historial

        futuro_ordenado = futuro.sort_values(
            by=[self.configuracion.columna_fecha, "ZonaCBAID"]
        ).reset_index(drop=True)
        filas_salida: list[dict[str, object]] = []
        for _, fila in futuro_ordenado.iterrows():
            zona_id = int(fila["ZonaCBAID"])
            historial = historial_por_zona[zona_id]
            fila_modelo = fila.to_dict()
            fila_modelo["lag_1"] = float(historial[-1])
            fila_modelo["lag_3"] = float(historial[-3])
            prediccion = float(modelo.predict(pd.DataFrame([fila_modelo]))[0])
            historial.append(prediccion)

            fila_salida = {
                "FechaMes": fila["FechaMes"],
                "Anio": fila["Anio"],
                "Mes": fila["Mes"],
                "Trimestre": fila["Trimestre"],
                "ZonaCBAID": fila["ZonaCBAID"],
                "NombreZona": fila["NombreZona"],
                self.configuracion.columna_objetivo: fila.get(self.configuracion.columna_objetivo),
                "CantidadCategorias": fila["CantidadCategorias"],
                "lag_1": fila_modelo["lag_1"],
                "lag_3": fila_modelo["lag_3"],
                "TipoCambioPromedioMensual": fila["TipoCambioPromedioMensual"],
                "PrecioCombustiblePromedioMensual": fila["PrecioCombustiblePromedioMensual"],
                "TempMaxProm": fila["TempMaxProm"],
                "TempMinProm": fila["TempMinProm"],
                "PrecipitacionProm": fila["PrecipitacionProm"],
                "HumedadProm": fila["HumedadProm"],
                "RadiacionSolarProm": fila["RadiacionSolarProm"],
                "FlagFinAnio": fila["FlagFinAnio"],
                "PrediccionCBA_TotalMensual": prediccion,
            }
            filas_salida.append(fila_salida)

        return pd.DataFrame(filas_salida)

    @staticmethod
    def _precision_desde_arrays(real: np.ndarray, pred: np.ndarray) -> float:
        real = np.asarray(real, dtype=float)
        pred = np.asarray(pred, dtype=float)
        denominador = np.where(np.abs(real) < 1e-9, 1.0, np.abs(real))
        mape = float(np.mean(np.abs(real - pred) / denominador))
        return max(0.0, (1.0 - mape) * 100.0)

    @staticmethod
    def _ruta_modelo_algoritmo(ruta_base: Path, algoritmo: str) -> Path:
        stem = ruta_base.stem
        suffix = ruta_base.suffix or ".joblib"
        return ruta_base.with_name(f"{stem}_{algoritmo}{suffix}")

    @staticmethod
    def _nombre_columna_algoritmo(algoritmo: str) -> str:
        partes = algoritmo.strip().lower().split("_")
        return "".join(parte.capitalize() for parte in partes)
