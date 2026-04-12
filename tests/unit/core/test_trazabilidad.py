from __future__ import annotations

import pandas as pd
import pytest

from trazabilidad import ValidadorTrazabilidad, validar_columnas_obligatorias


def test_validador_tolerates_datos_consistentes_entre_etapas() -> None:
    validador = ValidadorTrazabilidad(
        "clima",
        ("zona", "anio", "mes"),
        ("precipitacion", "humedad"),
    )

    validador.registrar_dataframe(
        "origen",
        pd.DataFrame(
            [
                {"zona": "MATINA", "anio": 2024, "mes": 1, "precipitacion": 4.5, "humedad": 80.0}
            ]
        ),
    )
    validador.registrar_dataframe(
        "transformado",
        pd.DataFrame(
            [
                {"zona": "MATINA", "anio": 2024, "mes": 1, "precipitacion": 4.5, "humedad": 80.0}
            ]
        ),
    )


def test_validador_falla_si_un_valor_no_nulo_se_pierde() -> None:
    validador = ValidadorTrazabilidad(
        "clima",
        ("zona", "anio", "mes"),
        ("precipitacion", "humedad"),
    )
    validador.registrar_dataframe(
        "origen",
        pd.DataFrame(
            [
                {"zona": "MATINA", "anio": 2024, "mes": 1, "precipitacion": 4.5, "humedad": 80.0}
            ]
        ),
    )

    with pytest.raises(RuntimeError, match="Trazabilidad rota"):
        validador.registrar_dataframe(
            "transformado",
            pd.DataFrame(
                [
                    {"zona": "MATINA", "anio": 2024, "mes": 1, "precipitacion": None, "humedad": 80.0}
                ]
            ),
        )


def test_validar_columnas_obligatorias_falla_con_nulos() -> None:
    with pytest.raises(ValueError, match="columnas obligatorias"):
        validar_columnas_obligatorias(
            pd.DataFrame([{"fecha": "2024-01-01", "compra": None, "venta": 10.0}]),
            ("fecha", "compra", "venta"),
            "tipo_cambio/origen",
        )
