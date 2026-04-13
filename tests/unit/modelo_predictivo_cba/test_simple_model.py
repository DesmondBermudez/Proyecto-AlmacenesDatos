from __future__ import annotations

import pandas as pd

from modelo_predictivo_cba.models import ConfiguracionModeloCBA
from modelo_predictivo_cba.simple_model import ModeloLinealSimpleCBA


def _dataframe_entrenamiento() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "FechaMes": "2024-01-01",
                "Anio": 2024,
                "Mes": 1,
                "ZonaCBAID": 1,
                "NombreZona": "RURAL",
                "CBA_TotalMensual": 100.0,
                "CantidadCategorias": 15,
                "lag_1": 90.0,
                "lag_3": 88.0,
                "TipoCambioPromedioMensual": 520.0,
                "PrecioCombustiblePromedioMensual": 700.0,
                "TempMaxProm": 30.0,
                "TempMinProm": 22.0,
                "PrecipitacionProm": 7.0,
                "HumedadProm": 80.0,
                "RadiacionSolarProm": 5.0,
                "FlagFinAnio": 0,
            },
            {
                "FechaMes": "2024-02-01",
                "Anio": 2024,
                "Mes": 2,
                "ZonaCBAID": 1,
                "NombreZona": "RURAL",
                "CBA_TotalMensual": 110.0,
                "CantidadCategorias": 15,
                "lag_1": 100.0,
                "lag_3": 89.0,
                "TipoCambioPromedioMensual": 525.0,
                "PrecioCombustiblePromedioMensual": 710.0,
                "TempMaxProm": 31.0,
                "TempMinProm": 22.5,
                "PrecipitacionProm": 6.0,
                "HumedadProm": 81.0,
                "RadiacionSolarProm": 5.3,
                "FlagFinAnio": 0,
            },
            {
                "FechaMes": "2024-01-01",
                "Anio": 2024,
                "Mes": 1,
                "ZonaCBAID": 2,
                "NombreZona": "URBANA",
                "CBA_TotalMensual": 120.0,
                "CantidadCategorias": 15,
                "lag_1": 110.0,
                "lag_3": 105.0,
                "TipoCambioPromedioMensual": 520.0,
                "PrecioCombustiblePromedioMensual": 700.0,
                "TempMaxProm": 30.0,
                "TempMinProm": 22.0,
                "PrecipitacionProm": 7.0,
                "HumedadProm": 80.0,
                "RadiacionSolarProm": 5.0,
                "FlagFinAnio": 0,
            },
            {
                "FechaMes": "2024-02-01",
                "Anio": 2024,
                "Mes": 2,
                "ZonaCBAID": 2,
                "NombreZona": "URBANA",
                "CBA_TotalMensual": 130.0,
                "CantidadCategorias": 15,
                "lag_1": 120.0,
                "lag_3": 109.0,
                "TipoCambioPromedioMensual": 525.0,
                "PrecioCombustiblePromedioMensual": 710.0,
                "TempMaxProm": 31.0,
                "TempMinProm": 22.5,
                "PrecipitacionProm": 6.0,
                "HumedadProm": 81.0,
                "RadiacionSolarProm": 5.3,
                "FlagFinAnio": 0,
            },
        ]
    )


def test_modelo_lineal_simple_entrena_y_predice_sin_nulos() -> None:
    modelo = ModeloLinealSimpleCBA(ConfiguracionModeloCBA())
    df = _dataframe_entrenamiento()

    modelo.fit(df)
    predicciones = modelo.predict(df)

    assert len(predicciones) == len(df)
    assert all(prediccion >= 0 for prediccion in predicciones)


def test_modelo_lineal_simple_guarda_y_recarga_artefacto(local_tmp_path) -> None:
    modelo = ModeloLinealSimpleCBA(ConfiguracionModeloCBA(), algoritmo="random_forest")
    df = _dataframe_entrenamiento()
    ruta = local_tmp_path / "modelo.joblib"

    modelo.fit(df)
    modelo.guardar(ruta)
    recargado = ModeloLinealSimpleCBA.cargar(ruta, configuracion=ConfiguracionModeloCBA())

    assert ruta.exists()
    assert recargado.algoritmo == "random_forest"
    assert recargado.predict(df).shape[0] == len(df)
