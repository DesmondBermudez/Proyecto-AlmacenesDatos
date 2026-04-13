from __future__ import annotations

from datetime import datetime
from pathlib import Path

from etl_cba.extract import ExtractorCBAOficial, normalizar_fecha_inec


DATA_CBA_DIR = Path(__file__).resolve().parents[3] / "etl" / "data" / "raw" / "cba"


def test_normalizar_fecha_inec_convierte_timestamp_y_serial_excel() -> None:
    serial = (datetime(2011, 9, 1) - datetime(1899, 12, 30)).days

    assert normalizar_fecha_inec(datetime(2011, 9, 1)) == "set-11"
    assert normalizar_fecha_inec(serial) == "set-11"


def test_extractor_cba_oficial_extrae_detalle_y_control_desde_archivos_reales() -> None:
    extractor = ExtractorCBAOficial(DATA_CBA_DIR)

    resultado = extractor.extraer()

    assert not resultado.detalle.empty
    assert not resultado.consolidado.empty
    assert {"Nacional", "Urbano", "Rural"} <= set(resultado.detalle["Zona"])
    assert {"NACIONAL", "URBANO", "RURAL"} <= set(resultado.consolidado["Zona"].str.upper())
    assert "CBA" in set(resultado.detalle["CategoriaNombre"].astype(str).str.upper())
