from __future__ import annotations

from etl_combustible.models import FUENTE_RESPALDO
from etl_combustible.transform import TransformadorCombustible


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
