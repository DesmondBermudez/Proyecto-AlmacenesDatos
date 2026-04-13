from __future__ import annotations

import pandas as pd

from modelo_predictivo_cba.models import ConfiguracionModeloCBA
from modelo_predictivo_cba.service import ServicioModeloCBA


class RepositorioStub:
    def __init__(
        self,
        dataframe_entrenamiento: pd.DataFrame,
        dataframe_prediccion: pd.DataFrame,
        configuracion: ConfiguracionModeloCBA,
    ) -> None:
        self.dataframe_entrenamiento = dataframe_entrenamiento
        self.dataframe_prediccion = dataframe_prediccion
        self.configuracion = configuracion

    def cargar_entrenamiento(self) -> pd.DataFrame:
        return self.dataframe_entrenamiento.copy()

    def cargar_prediccion(self) -> pd.DataFrame:
        return self.dataframe_prediccion.copy()

    def validar_vista_entrenamiento(self):
        return list(self.configuracion.columnas_requeridas_entrenamiento)

    def validar_vista_prediccion(self):
        return list(self.configuracion.columnas_requeridas_prediccion)

    @property
    def db(self):
        raise RuntimeError("db no disponible en stub")


def _df_base() -> pd.DataFrame:
    filas = []
    for indice_mes, fecha in enumerate(
        pd.date_range("2023-01-01", periods=36, freq="MS"),
        start=1,
    ):
        for zona_id, zona, base_valor in ((1, "RURAL", 100.0), (2, "URBANA", 120.0)):
            filas.append(
                {
                    "FechaMes": fecha,
                    "Anio": fecha.year,
                    "Mes": fecha.month,
                    "Trimestre": ((fecha.month - 1) // 3) + 1,
                    "ZonaCBAID": zona_id,
                    "NombreZona": zona,
                    "CBA_TotalMensual": base_valor + indice_mes,
                    "CantidadCategorias": 15,
                    "lag_1": base_valor + indice_mes - 1,
                    "lag_3": base_valor + indice_mes - 3,
                    "TipoCambioPromedioMensual": 520.0 + indice_mes,
                    "PrecioCombustiblePromedioMensual": 700.0 + indice_mes,
                    "TempMaxProm": 30.0 + (indice_mes * 0.1),
                    "TempMinProm": 22.0 + (indice_mes * 0.1),
                    "PrecipitacionProm": 7.0 + (indice_mes * 0.1),
                    "HumedadProm": 80.0 + (indice_mes * 0.1),
                    "RadiacionSolarProm": 5.0 + (indice_mes * 0.1),
                    "FlagFinAnio": 0,
                }
            )
    return pd.DataFrame(filas)


def test_servicio_modelo_cba_entrena_y_genera_predicciones(local_tmp_path) -> None:
    configuracion = ConfiguracionModeloCBA(
        ruta_modelo=local_tmp_path / "modelo.joblib",
        ruta_predicciones=local_tmp_path / "predicciones_2027.csv",
        ruta_validacion=local_tmp_path / "validacion_2025.csv",
        precision_minima_pct=70.0,
    )
    servicio = ServicioModeloCBA.__new__(ServicioModeloCBA)
    servicio.configuracion = configuracion
    dataframe = _df_base()
    futuro = pd.DataFrame(
        [
            {
                "FechaMes": pd.Timestamp("2027-04-01"),
                "Anio": 2027,
                "Mes": 4,
                "Trimestre": 2,
                "ZonaCBAID": 1,
                "NombreZona": "RURAL",
                "CantidadCategorias": 15,
                "TipoCambioPromedioMensual": 560.0,
                "PrecioCombustiblePromedioMensual": 740.0,
                "TempMaxProm": 31.5,
                "TempMinProm": 23.5,
                "PrecipitacionProm": 8.5,
                "HumedadProm": 81.5,
                "RadiacionSolarProm": 6.5,
                "FlagFinAnio": 0,
            },
            {
                "FechaMes": pd.Timestamp("2027-04-01"),
                "Anio": 2027,
                "Mes": 4,
                "Trimestre": 2,
                "ZonaCBAID": 2,
                "NombreZona": "URBANA",
                "CantidadCategorias": 15,
                "TipoCambioPromedioMensual": 560.0,
                "PrecioCombustiblePromedioMensual": 740.0,
                "TempMaxProm": 31.5,
                "TempMinProm": 23.5,
                "PrecipitacionProm": 8.5,
                "HumedadProm": 81.5,
                "RadiacionSolarProm": 6.5,
                "FlagFinAnio": 0,
            },
        ]
    )
    servicio.repositorio = RepositorioStub(
        dataframe_entrenamiento=dataframe,
        dataframe_prediccion=futuro,
        configuracion=configuracion,
    )
    servicio.comparar_cba_con_fuente_xlsx = lambda ruta_salida=None: local_tmp_path / "comparacion.csv"

    resumen = servicio.entrenar()
    resultado = servicio.predecir()

    assert set(resumen.rutas_modelos) == set(configuracion.algoritmos_candidatos)
    assert all(ruta.exists() for ruta in resumen.rutas_modelos.values())
    assert resumen.ruta_validacion is not None
    assert resumen.ruta_validacion.exists()
    assert resumen.metricas_algoritmos
    assert {item["algoritmo"] for item in resumen.metricas_algoritmos} == set(configuracion.algoritmos_candidatos)
    assert resultado.ruta_predicciones.exists()
    assert resultado.filas_generadas == len(futuro)
    assert set(resultado.algoritmos_utilizados) == set(configuracion.algoritmos_candidatos)
    assert resultado.fecha_inicio_prediccion == "2027-04-01"
    salida = pd.read_csv(resultado.ruta_predicciones, encoding="utf-8-sig")
    assert "PrediccionCBA_Lineal" in salida.columns
    assert "PrediccionCBA_RandomForest" in salida.columns


def test_servicio_valida_vistas_emparejadas_con_el_modelo() -> None:
    configuracion = ConfiguracionModeloCBA()
    servicio = ServicioModeloCBA.__new__(ServicioModeloCBA)
    servicio.configuracion = configuracion

    class RepositorioValidacionStub:
        def validar_vista_entrenamiento(self):
            return list(configuracion.columnas_requeridas_entrenamiento)

        def validar_vista_prediccion(self):
            return list(configuracion.columnas_requeridas_prediccion)

    servicio.repositorio = RepositorioValidacionStub()

    resultado = servicio.validar_vistas()

    assert resultado.vista_entrenamiento == configuracion.vista_entrenamiento
    assert resultado.vista_prediccion == configuracion.vista_prediccion
    assert "CBA_TotalMensual" in resultado.columnas_entrenamiento
    assert "CBA_TotalMensual" not in resultado.columnas_prediccion


def test_servicio_pipeline_orquesta_validacion_entrenamiento_y_prediccion(local_tmp_path) -> None:
    configuracion = ConfiguracionModeloCBA(
        ruta_modelo=local_tmp_path / "modelo.joblib",
        ruta_predicciones=local_tmp_path / "predicciones_2027.csv",
        ruta_validacion=local_tmp_path / "validacion_2025.csv",
        precision_minima_pct=70.0,
    )
    servicio = ServicioModeloCBA.__new__(ServicioModeloCBA)
    servicio.configuracion = configuracion
    dataframe = _df_base()
    futuro = pd.DataFrame(
        [
            {
                "FechaMes": pd.Timestamp("2027-04-01"),
                "Anio": 2027,
                "Mes": 4,
                "Trimestre": 2,
                "ZonaCBAID": 1,
                "NombreZona": "RURAL",
                "CantidadCategorias": 15,
                "TipoCambioPromedioMensual": 560.0,
                "PrecioCombustiblePromedioMensual": 740.0,
                "TempMaxProm": 31.5,
                "TempMinProm": 23.5,
                "PrecipitacionProm": 8.5,
                "HumedadProm": 81.5,
                "RadiacionSolarProm": 6.5,
                "FlagFinAnio": 0,
            }
        ]
    )
    servicio.repositorio = RepositorioStub(
        dataframe_entrenamiento=dataframe,
        dataframe_prediccion=futuro,
        configuracion=configuracion,
    )
    servicio.comparar_cba_con_fuente_xlsx = lambda ruta_salida=None: local_tmp_path / "comparacion.csv"

    resultado = servicio.pipeline()

    assert resultado.validacion.vista_entrenamiento == configuracion.vista_entrenamiento
    assert all(ruta.exists() for ruta in resultado.entrenamiento.rutas_modelos.values())
    assert resultado.entrenamiento.ruta_validacion is not None
    assert resultado.entrenamiento.ruta_validacion.exists()
    assert resultado.prediccion.ruta_predicciones.exists()
