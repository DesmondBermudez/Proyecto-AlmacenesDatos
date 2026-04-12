from __future__ import annotations

import pandas as pd

from etl_dolar_canasta.models import FUENTE_RESPALDO
from etl_dolar_canasta.transform import TransformadorCanasta, TransformadorCombustible


def test_transformador_combustible_normaliza_y_preserva_fuente() -> None:
    transformador = TransformadorCombustible()

    productos, precios = transformador.transformar(
        [
            {
                "producto": "Gasolina RON 95",
                "precioFinal": 780.0,
                "fechaPublicacion": "2026-04-11T00:00:00",
                "fuente_id": FUENTE_RESPALDO,
            },
            {
                "producto": "Diésel",
                "precioFinal": 690.0,
                "fechaPublicacion": "2026-04-11T00:00:00",
                "fuente_id": FUENTE_RESPALDO,
            },
        ]
    )

    assert [producto.nombre_normalizado for producto in productos] == [
        "Gasolina RON 95",
        "Diesel",
    ]
    assert all(producto.fuente_id == FUENTE_RESPALDO for producto in productos)
    assert all(precio.fuente_id == FUENTE_RESPALDO for precio in precios)


def test_transformador_canasta_limpia_columnas_y_descarta_precios_invalidos(local_tmp_path) -> None:
    ruta_csv = local_tmp_path / "canasta.csv"
    pd.DataFrame(
        [
            {
                "Fecha": "2026-04-01",
                "NombreProducto": " arroz ",
                "Categoria": "cereales",
                "EsImportado": 0,
                "UnidadMedida": "kg",
                "Provincia": "san jose ",
                "Canton": " central",
                "Distrito": "carmen ",
                "PrecioColones": "820.5",
                "PrecioBaseReferencia": 800,
                "FactorCanasta": 1.0,
            },
            {
                "Fecha": "2026-04-01",
                "NombreProducto": "frijoles",
                "Categoria": "leguminosas",
                "EsImportado": 0,
                "UnidadMedida": "kg",
                "Provincia": "cartago",
                "Canton": "cartago",
                "Distrito": "oriental",
                "PrecioColones": "no-num",
                "PrecioBaseReferencia": 1000,
                "FactorCanasta": 1.0,
            },
        ]
    ).to_csv(ruta_csv, index=False)

    df = TransformadorCanasta().leer_y_transformar(ruta_csv)

    assert len(df) == 1
    assert df.iloc[0]["NombreProducto"] == "ARROZ"
    assert df.iloc[0]["Provincia"] == "SAN JOSE"
    assert df.iloc[0]["Fecha"] == "2026-04-01"
