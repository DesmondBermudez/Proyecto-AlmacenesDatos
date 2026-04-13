from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass(slots=True)
class ConfiguracionModeloCBA:
    vista_entrenamiento: str = "dbo.vw_CBA_ModeloSimple_Entrenamiento"
    vista_prediccion: str = "dbo.vw_CBA_ModeloSimple_Prediccion"
    columna_objetivo: str = "CBA_TotalMensual"
    columna_fecha: str = "FechaMes"
    columnas_id: tuple[str, ...] = ("FechaMes", "ZonaCBAID", "NombreZona")
    columnas_categoricas: tuple[str, ...] = ("NombreZona",)
    columnas_numericas_modelo: tuple[str, ...] = (
        "Anio",
        "Mes",
        "CantidadCategorias",
        "lag_1",
        "lag_3",
        "TipoCambioPromedioMensual",
        "PrecioCombustiblePromedioMensual",
        "TempMaxProm",
        "TempMinProm",
        "PrecipitacionProm",
        "HumedadProm",
        "RadiacionSolarProm",
        "FlagFinAnio",
    )
    columnas_numericas_prediccion_base: tuple[str, ...] = (
        "Anio",
        "Mes",
        "CantidadCategorias",
        "TipoCambioPromedioMensual",
        "PrecioCombustiblePromedioMensual",
        "TempMaxProm",
        "TempMinProm",
        "PrecipitacionProm",
        "HumedadProm",
        "RadiacionSolarProm",
        "FlagFinAnio",
    )
    columnas_lags: tuple[str, ...] = ("lag_1", "lag_3")
    algoritmos_candidatos: tuple[str, ...] = ("random_forest", "lineal")
    algoritmo_por_defecto: str = "random_forest"
    horizonte_prediccion_meses: int = 12
    anio_validacion_preferido: int = 2025
    precision_minima_pct: float = 85.0
    ruta_modelo: Path = field(default_factory=lambda: Path("etl") / "data" / "processed" / "modelo_cba_simple.joblib")
    ruta_predicciones: Path = field(
        default_factory=lambda: Path("etl") / "data" / "processed" / "predicciones_cba_2027.csv"
    )
    ruta_validacion: Path = field(
        default_factory=lambda: Path("etl") / "data" / "processed" / "validacion_cba_2025.csv"
    )
    ruta_correlacion: Path = field(
        default_factory=lambda: Path("etl") / "data" / "processed" / "correlacion_cba_vs_exogenas.csv"
    )

    @property
    def columnas_features_modelo(self) -> tuple[str, ...]:
        return self.columnas_categoricas + self.columnas_numericas_modelo

    @property
    def columnas_features_prediccion(self) -> tuple[str, ...]:
        return self.columnas_categoricas + self.columnas_numericas_prediccion_base + self.columnas_lags

    @property
    def columnas_exogenas_correlacion(self) -> tuple[str, ...]:
        return (
            "TipoCambioPromedioMensual",
            "PrecioCombustiblePromedioMensual",
            "TempMaxProm",
            "TempMinProm",
            "PrecipitacionProm",
            "HumedadProm",
            "RadiacionSolarProm",
        )

    @property
    def columnas_requeridas_entrenamiento(self) -> tuple[str, ...]:
        return self.columnas_id + (self.columna_objetivo,) + tuple(
            columna
            for columna in self.columnas_features_modelo
            if columna not in self.columnas_id and columna != self.columna_objetivo
        )

    @property
    def columnas_requeridas_prediccion(self) -> tuple[str, ...]:
        return self.columnas_id + tuple(
            columna
            for columna in (self.columnas_categoricas + self.columnas_numericas_prediccion_base)
            if columna not in self.columnas_id
        )


@dataclass(slots=True)
class ArtefactoModeloCBA:
    version: str
    generado_en: str
    vista_entrenamiento: str
    vista_prediccion: str
    columna_objetivo: str
    algoritmo: str
    columnas_categoricas: list[str]
    columnas_numericas_modelo: list[str]
    categorias: dict[str, list[str]]
    etiquetas_diseno: list[str]
    estado_modelo: dict[str, object]
    metricas_algoritmos: list[dict[str, object]]


@dataclass(slots=True)
class ResumenEntrenamientoModeloCBA:
    filas_entrenamiento: int
    filas_validacion: int
    precision_minima_pct: float
    tiempo_total_entrenamiento_segundos: float
    metricas_algoritmos: list[dict[str, object]]
    comparacion_algoritmos: dict[str, object] | None
    rutas_modelos: dict[str, Path]
    ruta_validacion: Path | None


@dataclass(slots=True)
class ResultadoPrediccionModeloCBA:
    filas_generadas: int
    ruta_predicciones: Path
    algoritmos_utilizados: list[str]
    fecha_inicio_prediccion: str
    fecha_fin_prediccion: str
    metricas_algoritmos: list[dict[str, object]] = field(default_factory=list)
    comparacion_algoritmos: dict[str, object] | None = None


@dataclass(slots=True)
class ResultadoValidacionVistasCBA:
    vista_entrenamiento: str
    vista_prediccion: str
    columnas_entrenamiento: list[str]
    columnas_prediccion: list[str]


@dataclass(slots=True)
class ResultadoPipelineModeloCBA:
    validacion: ResultadoValidacionVistasCBA
    entrenamiento: ResumenEntrenamientoModeloCBA
    prediccion: ResultadoPrediccionModeloCBA


def crear_metadatos_base(configuracion: ConfiguracionModeloCBA) -> dict[str, str]:
    return {
        "version": "1.0",
        "generado_en": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "vista_entrenamiento": configuracion.vista_entrenamiento,
        "vista_prediccion": configuracion.vista_prediccion,
        "columna_objetivo": configuracion.columna_objetivo,
    }
