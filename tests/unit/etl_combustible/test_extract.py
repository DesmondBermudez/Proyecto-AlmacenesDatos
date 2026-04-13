from __future__ import annotations

import pandas as pd
import pytest

from etl_combustible.extract import ExtractorCombustible
from etl_combustible.models import FUENTE_ARESEP, FUENTE_RESPALDO


class ResponseStub:
    def __init__(self, payload: dict | list[dict]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict | list[dict]:
        return self.payload


def test_combustible_hace_fallback_a_csv(
    monkeypatch: pytest.MonkeyPatch, local_tmp_path
) -> None:
    ruta_csv = local_tmp_path / "combustible.csv"
    pd.DataFrame(
        [
            {
                "producto": "Gasolina RON 95",
                "precioFinal": 780.5,
                "fechaPublicacion": "2026-04-10T00:00:00",
            }
        ]
    ).to_csv(ruta_csv, index=False)
    extractor = ExtractorCombustible(ruta_csv)

    monkeypatch.setattr(
        "etl_combustible.extract.requests.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("API fuera")),
    )

    registros = extractor.obtener(guardar_csv=False)

    assert len(registros) == 1
    assert registros[0]["fuente_id"] == FUENTE_RESPALDO
    assert ruta_csv.exists()


def test_combustible_simula_si_no_hay_api_ni_csv(
    monkeypatch: pytest.MonkeyPatch, local_tmp_path
) -> None:
    extractor = ExtractorCombustible(local_tmp_path / "combustible.csv")

    monkeypatch.setattr(
        "etl_combustible.extract.requests.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("API fuera")),
    )

    registros = extractor.obtener(guardar_csv=False)

    assert len(registros) == 3
    assert {registro["producto"] for registro in registros} == {
        "Gasolina RON 95",
        "Gasolina RON 91",
        "Diesel",
    }
    assert all(registro["fuente_id"] == FUENTE_RESPALDO for registro in registros)


def test_combustible_usa_api_y_fuente_oficial(
    monkeypatch: pytest.MonkeyPatch, local_tmp_path
) -> None:
    extractor = ExtractorCombustible(local_tmp_path / "combustible.csv")
    llamadas: list[tuple] = []

    monkeypatch.setattr(
        "etl_combustible.extract.requests.get",
        lambda *args, **kwargs: (
            llamadas.append((args, kwargs)),
            ResponseStub(
                {
                    "value": [
                        {
                            "producto": "Gasolina RON 91",
                            "precioFinal": 755.0,
                            "fechaPublicacion": "2026-04-11T00:00:00",
                        }
                    ]
                }
            ),
        )[1],
    )

    registros = extractor.obtener(guardar_csv=False)

    assert len(registros) == 1
    assert registros[0]["fuente_id"] == FUENTE_ARESEP
    assert len(llamadas) == 1


def test_combustible_sobrescribe_csv_en_modo_historico(local_tmp_path) -> None:
    ruta_csv = local_tmp_path / "combustible.csv"
    pd.DataFrame(
        [{"producto": "Viejo", "precioFinal": 1.0, "fechaPublicacion": "2020-01-01T00:00:00"}]
    ).to_csv(ruta_csv, index=False)
    extractor = ExtractorCombustible(ruta_csv)

    extractor._guardar_csv(
        [
            {
                "producto": "Gasolina RON 95",
                "precioFinal": 780.5,
                "fechaPublicacion": "2026-04-10T00:00:00",
                "fuente_id": FUENTE_RESPALDO,
            }
        ],
        sobrescribir=True,
    )
    resultado = pd.read_csv(ruta_csv)

    assert "Viejo" not in set(resultado["producto"].astype(str))


def test_combustible_falla_si_todas_las_fuentes_fallan(
    monkeypatch: pytest.MonkeyPatch, local_tmp_path
) -> None:
    extractor = ExtractorCombustible(local_tmp_path / "combustible.csv")

    monkeypatch.setattr(extractor, "_obtener_api", lambda: (_ for _ in ()).throw(RuntimeError("api")))
    monkeypatch.setattr(extractor, "_leer_csv", lambda: (_ for _ in ()).throw(RuntimeError("csv")))
    monkeypatch.setattr(extractor, "_simular_registros", lambda: (_ for _ in ()).throw(RuntimeError("sim")))

    with pytest.raises(RuntimeError, match="historico de combustibles"):
        extractor.obtener(guardar_csv=False)
