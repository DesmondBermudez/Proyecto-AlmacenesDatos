from __future__ import annotations

from datetime import date

from etl_dolar.models import FUENTE_HACIENDA, RegistroTipoCambio


def test_registro_tipo_cambio_usa_defaults_del_dominio() -> None:
    registro = RegistroTipoCambio(fecha=date(2026, 4, 12), compra=500.0, venta=505.0)

    assert registro.moneda_base_id == 1
    assert registro.moneda_referencia_id == 2
    assert registro.fuente_id == FUENTE_HACIENDA
