from __future__ import annotations

import pandas as pd
import pytest

from etl_cba.validation import ValidadorCBAOficial


def test_validador_cba_reconcilia_consolidado_con_total_cba() -> None:
    detalle = pd.DataFrame(
        [
            {"FechaID": 20260401, "Zona": "NACIONAL", "CategoriaNombre": "CBA", "CostoPerCapita": 65000.0},
            {"FechaID": 20260401, "Zona": "NACIONAL", "CategoriaNombre": "CEREALES", "CostoPerCapita": 12000.0},
        ]
    )
    consolidado = pd.DataFrame(
        [
            {"FechaID": 20260401, "Zona": "NACIONAL", "CostoPerCapitaControl": 65000.0},
        ]
    )

    comparacion = ValidadorCBAOficial().validar_reconciliacion(detalle, consolidado)

    assert len(comparacion) == 1
    assert float(comparacion.iloc[0]["DiferenciaAbsoluta"]) == 0.0


def test_validador_cba_falla_si_consolidado_no_coincide() -> None:
    detalle = pd.DataFrame(
        [
            {"FechaID": 20260401, "Zona": "NACIONAL", "CategoriaNombre": "CBA", "CostoPerCapita": 65000.0},
        ]
    )
    consolidado = pd.DataFrame(
        [
            {"FechaID": 20260401, "Zona": "NACIONAL", "CostoPerCapitaControl": 65010.0},
        ]
    )

    with pytest.raises(RuntimeError, match="consolidado mensual"):
        ValidadorCBAOficial().validar_reconciliacion(detalle, consolidado)
