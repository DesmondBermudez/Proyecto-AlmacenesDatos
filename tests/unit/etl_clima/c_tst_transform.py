from __future__ import annotations

import pandas as pd

from etl_clima.transform import TransformadorClima


def test_transformador_clima_normaliza_columnas_base() -> None:
    df = pd.DataFrame(
        [
            {
                "Zona": " matina ",
                "Latitud": "10.00",
                "Longitud": "-83.35",
                "Anio": "2024",
                "Mes": "1",
                "Temp_Max": "30.5",
                "Temp_Min": "22.1",
                "Precipitacion": "5.2",
                "Humedad": "83.0",
                "RadiacionSolar": "4.7",
            }
        ]
    )

    resultado = TransformadorClima().transformar(df)

    assert resultado.iloc[0]["zona"] == "MATINA"
    assert int(resultado.iloc[0]["anio"]) == 2024
    assert int(resultado.iloc[0]["mes"]) == 1
