from __future__ import annotations

from datetime import date

from etl_dolar_canasta.models import (
    FUENTE_ARESEP,
    FUENTE_HACIENDA,
    RegistroPrecioCombustible,
    RegistroProductoCombustible,
    RegistroTipoCambio,
)


def test_registro_tipo_cambio_usa_defaults_del_dominio() -> None:
    registro = RegistroTipoCambio(fecha=date(2026, 4, 12), compra=500.0, venta=505.0)

    assert registro.moneda_base_id == 1
    assert registro.moneda_referencia_id == 2
    assert registro.fuente_id == FUENTE_HACIENDA


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
