from __future__ import annotations

import pandas as pd

from etl_cba.models import FUENTE_INEC
from etl_cba.transform import TransformadorCBA


def test_transformador_cba_normaliza_detalle_oficial() -> None:
    transformador = TransformadorCBA()
    df = pd.DataFrame(
        [
            {
                "Zona": " Nacional ",
                "CategoriaNombre": " cba ",
                "PeriodoTextoOriginal": "set-11",
                "CostoPerCapita": "1234.5",
                "ArchivoOrigen": "archivo.xlsx",
            }
        ]
    )

    resultado = transformador.transformar_detalle(df)

    assert len(resultado) == 1
    assert resultado.iloc[0]["Fecha"] == "2011-09-01"
    assert int(resultado.iloc[0]["FechaID"]) == 20110901
    assert resultado.iloc[0]["Zona"] == "NACIONAL"
    assert resultado.iloc[0]["CategoriaNombre"] == "CBA"
    assert int(resultado.iloc[0]["FuenteID"]) == FUENTE_INEC


def test_transformador_cba_normaliza_consolidado_control() -> None:
    transformador = TransformadorCBA()
    df = pd.DataFrame(
        [
            {
                "Fecha": "2026-04-01",
                "FechaID": "20260401",
                "Zona": " urbano ",
                "CostoPerCapitaControl": "65000.5",
                "ArchivoOrigenControl": "control.xlsx",
            }
        ]
    )

    resultado = transformador.transformar_control(df)

    assert len(resultado) == 1
    assert resultado.iloc[0]["Fecha"] == "2026-04-01"
    assert int(resultado.iloc[0]["FechaID"]) == 20260401
    assert resultado.iloc[0]["Zona"] == "URBANO"
