from __future__ import annotations

import pandas as pd

from etl_clima.load import CargadorClima


def test_cargador_clima_guarda_csv(local_tmp_path) -> None:
    ruta_salida = local_tmp_path / "clima.csv"
    cargador = CargadorClima(ruta_salida)

    resultado = cargador.guardar_csv(
        pd.DataFrame(
            [
                {
                    "zona": "MATINA",
                    "anio": 2024,
                    "mes": 1,
                }
            ]
        )
    )

    assert resultado == ruta_salida
    assert ruta_salida.exists()
