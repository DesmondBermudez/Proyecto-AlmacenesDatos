from __future__ import annotations

import pandas as pd
import pytest

from etl_clima.extract import ExtractorClimaNASA
from etl_clima.models import ZonaClimatica


class ResponseStub:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


CSV_NASA_STUB = """-BEGIN HEADER-
NASA/POWER Source Native Resolution Monthly Data
-END HEADER-
PARAMETER,YEAR,JAN,FEB,MAR,APR,MAY,JUN,JUL,AUG,SEP,OCT,NOV,DEC,ANN
T2M_MAX,2024,30.5,31.0,,,,,,,,,,,30.8
T2M_MIN,2024,22.0,22.5,,,,,,,,,,,22.2
PRECTOTCORR,2024,4.5,6.1,,,,,,,,,,,5.3
RH2M,2024,83.0,81.0,,,,,,,,,,,82.0
ALLSKY_SFC_SW_DWN,2024,4.1,4.4,,,,,,,,,,,4.2
"""


def test_extractor_clima_expone_parametros_base_de_nasa() -> None:
    extractor = ExtractorClimaNASA()

    config = extractor.obtener_configuracion_peticion()

    assert config["community"] == "ag"
    assert config["format"] == "CSV"
    assert config["units"] == "metric"
    assert "T2M_MAX" in config["parameters"]
    assert "PRECTOT" in config["parameters"]


def test_extractor_clima_parsea_csv_y_descarta_agregado_13() -> None:
    extractor = ExtractorClimaNASA()

    resultado = extractor._parsear_respuesta_csv(
        CSV_NASA_STUB,
        ZonaClimatica(nombre="Matina", latitud=10.0, longitud=-83.35),
    )

    assert len(resultado) == 2
    assert set(resultado["Mes"].tolist()) == {1, 2}
    assert resultado.iloc[0]["Precipitacion"] == 4.5


def test_extractor_clima_consulta_api_y_guarda_csv(
    monkeypatch: pytest.MonkeyPatch, local_tmp_path
) -> None:
    ruta_csv = local_tmp_path / "clima.csv"
    extractor = ExtractorClimaNASA(ruta_respaldo_csv=ruta_csv)
    llamadas: list[tuple] = []

    monkeypatch.setattr(
        extractor,
        "listar_zonas_referencia",
        lambda: (ZonaClimatica(nombre="Matina", latitud=10.0, longitud=-83.35),),
    )
    monkeypatch.setattr(
        "etl_clima.extract.requests.get",
        lambda *args, **kwargs: (
            llamadas.append((args, kwargs)),
            ResponseStub(CSV_NASA_STUB),
        )[1],
    )

    resultado = extractor.obtener_desde_api(guardar_csv=True)

    assert isinstance(resultado, pd.DataFrame)
    assert len(resultado) == 2
    assert ruta_csv.exists()
    assert len(llamadas) == 1
    assert llamadas[0][1]["params"]["community"] == "ag"
    assert llamadas[0][1]["params"]["format"] == "CSV"


def test_extractor_clima_hace_fallback_a_csv_dummy(
    monkeypatch: pytest.MonkeyPatch, local_tmp_path
) -> None:
    ruta_csv = local_tmp_path / "clima.csv"
    pd.DataFrame(
        [
            {
                "Zona": "Matina",
                "Latitud": 10.0,
                "Longitud": -83.35,
                "Anio": 2024,
                "Mes": 1,
                "Temp_Max": 30.5,
                "Temp_Min": 22.1,
                "Precipitacion": 5.0,
                "Humedad": 84.0,
                "RadiacionSolar": 4.8,
            }
        ]
    ).to_csv(ruta_csv, index=False)
    extractor = ExtractorClimaNASA(ruta_respaldo_csv=ruta_csv)

    monkeypatch.setattr(
        extractor,
        "obtener_desde_api",
        lambda guardar_csv=True: (_ for _ in ()).throw(RuntimeError("API fuera")),
    )

    resultado = extractor.obtener(guardar_csv=False)

    assert len(resultado) == 1
    assert ruta_csv.exists()


def test_extractor_clima_combina_api_y_respaldo_para_rellenar_huecos(
    monkeypatch: pytest.MonkeyPatch, local_tmp_path
) -> None:
    ruta_csv = local_tmp_path / "clima.csv"
    pd.DataFrame(
        [
            {
                "Zona": "Matina",
                "Latitud": 10.0,
                "Longitud": -83.35,
                "Anio": 2011,
                "Mes": 1,
                "Temp_Max": 30.0,
                "Temp_Min": 22.0,
                "Precipitacion": 5.0,
                "Humedad": 84.0,
                "RadiacionSolar": 4.8,
            }
        ]
    ).to_csv(ruta_csv, index=False)
    extractor = ExtractorClimaNASA(ruta_respaldo_csv=ruta_csv)

    monkeypatch.setattr(
        extractor,
        "obtener_desde_api",
        lambda guardar_csv=False: pd.DataFrame(
            [
                {
                    "Zona": "Matina",
                    "Latitud": 10.0,
                    "Longitud": -83.35,
                    "Anio": 2011,
                    "Mes": 2,
                    "Temp_Max": 30.5,
                    "Temp_Min": 22.1,
                    "Precipitacion": 5.1,
                    "Humedad": 84.5,
                    "RadiacionSolar": 4.9,
                }
            ]
        ),
    )

    resultado = extractor.obtener(guardar_csv=True)

    assert len(resultado) == 2
    assert set(resultado["Mes"].tolist()) == {1, 2}
    df_guardado = pd.read_csv(ruta_csv)
    assert len(df_guardado) == 2


def test_extractor_clima_falla_si_api_y_csv_no_estan_disponibles(
    monkeypatch: pytest.MonkeyPatch, local_tmp_path
) -> None:
    extractor = ExtractorClimaNASA(ruta_respaldo_csv=local_tmp_path / "clima.csv")

    monkeypatch.setattr(
        extractor,
        "obtener_desde_api",
        lambda guardar_csv=True: (_ for _ in ()).throw(RuntimeError("API fuera")),
    )
    monkeypatch.setattr(extractor, "leer_respaldo_csv", lambda: pd.DataFrame())

    with pytest.raises(RuntimeError, match="NASA POWER ni desde el CSV de respaldo"):
        extractor.obtener(guardar_csv=False)


def test_extractor_clima_descarta_csv_sin_metricas_completas() -> None:
    extractor = ExtractorClimaNASA()
    resultado = extractor._parsear_respuesta_csv(
        """PARAMETER,YEAR,JAN,FEB,MAR,APR,MAY,JUN,JUL,AUG,SEP,OCT,NOV,DEC,ANN
T2M_MAX,2024,30.5,,,,,,,,,,,,
T2M_MIN,2024,22.0,,,,,,,,,,,,
PRECTOT,2024,-999,,,,,,,,,,,,
RH2M,2024,83.0,,,,,,,,,,,,
ALLSKY_SFC_SW_DWN,2024,4.1,,,,,,,,,,,,
""",
        ZonaClimatica(nombre="Matina", latitud=10.0, longitud=-83.35),
    )

    assert resultado.empty
