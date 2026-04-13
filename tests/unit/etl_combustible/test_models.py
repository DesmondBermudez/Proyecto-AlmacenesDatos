from __future__ import annotations

from etl_combustible.models import (
    FUENTE_ARESEP,
    RegistroPrecioCombustible,
    RegistroProductoCombustible,
)


def test_registros_combustible_usan_defaults_esperados() -> None:
    producto = RegistroProductoCombustible(
        nombre_raw="Gasolina RON 95",
        nombre_normalizado="Gasolina RON 95",
    )
    precio = RegistroPrecioCombustible(
        fecha_raw="2026-04-12T00:00:00",
        nombre_producto_raw="Gasolina RON 95",
        precio=785.0,
    )

    assert producto.fuente_id == FUENTE_ARESEP
    assert precio.fuente_id == FUENTE_ARESEP
