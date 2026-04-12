from __future__ import annotations

from etl_clima.extract import ExtractorClimaNASA


def test_extractor_clima_expone_parametros_base_de_nasa() -> None:
    extractor = ExtractorClimaNASA()

    config = extractor.obtener_configuracion_peticion()

    assert config["community"] == "AG"
    assert config["format"] == "JSON"
    assert "T2M_MAX" in config["parameters"]


def test_extractor_clima_carga_script_referencia() -> None:
    extractor = ExtractorClimaNASA()

    contenido = extractor.cargar_script_referencia()

    assert "power.larc.nasa.gov/api" in contenido
