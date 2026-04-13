from __future__ import annotations

from etl_cba.models import CONTROL_FILE_PATTERN, FUENTE_INEC, PRODUCT_FILE_PATTERNS


def test_modelos_cba_definen_fuente_y_patrones_oficiales() -> None:
    assert FUENTE_INEC == 5
    assert len(PRODUCT_FILE_PATTERNS) == 3
    assert CONTROL_FILE_PATTERN == "CBA_*XMES.xlsx"
