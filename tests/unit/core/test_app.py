from __future__ import annotations

import pandas as pd

from app import ETLApp


def test_normalizar_clima_deriva_fecha_id_desde_anio_y_mes() -> None:
    dataframe = pd.DataFrame(
        [
            {
                "Zona": "Matina",
                "Latitud": 10.0,
                "Longitud": -83.35,
                "Anio": 2024,
                "Mes": 2,
                "Temp_Max": 30.5,
                "Temp_Min": 22.0,
                "Precipitacion": 4.5,
                "Humedad": 83.0,
                "RadiacionSolar": 4.1,
            }
        ]
    )

    resultado = ETLApp._normalizar_clima(dataframe)

    assert list(resultado.columns) == [
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
    assert int(resultado.iloc[0]["fecha_id"]) == 20240201


def test_filtrar_tipo_cambio_csv_por_alcance_conserva_solo_fechas_procesadas() -> None:
    df_csv = pd.DataFrame(
        [
            {"fecha": "2000-01-01", "compra": 300.0, "venta": 302.0},
            {"fecha": "2026-04-12", "compra": 510.0, "venta": 514.0},
        ]
    )
    df_actual = pd.DataFrame([{"fecha": "2026-04-12", "compra": 510.0, "venta": 514.0}])

    resultado = ETLApp._filtrar_tipo_cambio_csv_por_alcance(df_csv, df_actual)

    assert len(resultado) == 1
    assert resultado.iloc[0]["fecha"] == "2026-04-12"
