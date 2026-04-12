from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from etl_dolar_canasta.extract import ExtractorCombustible, ExtractorTipoCambio
from etl_dolar_canasta.models import FUENTE_ARESEP, FUENTE_HACIENDA, FUENTE_RESPALDO


class ResponseStub:
    def __init__(self, payload: dict | list[dict]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict | list[dict]:
        return self.payload


def test_tipo_cambio_diario_usa_api_y_fuente_oficial(
    monkeypatch: pytest.MonkeyPatch, local_tmp_path
) -> None:
    extractor = ExtractorTipoCambio(local_tmp_path / "tipo_cambio.csv")
    llamadas: list[tuple] = []

    monkeypatch.setattr(
        "etl_dolar_canasta.extract.requests.get",
        lambda *args, **kwargs: (
            llamadas.append((args, kwargs)),
            ResponseStub(
                {
                    "compra": {"valor": "500.10"},
                    "venta": {"valor": "505.20", "fecha": "2026-04-11T00:00:00Z"},
                }
            ),
        )[1],
    )

    registro = extractor.obtener_diario(guardar_csv=False)

    assert registro.compra == 500.10
    assert registro.venta == 505.20
    assert registro.fuente_id == FUENTE_HACIENDA
    assert len(llamadas) == 1


def test_tipo_cambio_diario_hace_fallback_a_csv_dummy(
    monkeypatch: pytest.MonkeyPatch, local_tmp_path
) -> None:
    ruta_csv = local_tmp_path / "tipo_cambio.csv"
    pd.DataFrame(
        [{"fecha": "2026-04-10", "compra": 499.5, "venta": 504.5}]
    ).to_csv(ruta_csv, index=False)
    extractor = ExtractorTipoCambio(ruta_csv)

    monkeypatch.setattr(
        "etl_dolar_canasta.extract.requests.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("API fuera")),
    )

    registro = extractor.obtener_diario(guardar_csv=False)

    assert registro.fecha.isoformat() == "2026-04-10"
    assert registro.fuente_id == FUENTE_RESPALDO
    assert ruta_csv.exists()


def test_resolver_bloque_tipo_cambio_simula_si_no_hay_respaldo(
    monkeypatch: pytest.MonkeyPatch, local_tmp_path
) -> None:
    extractor = ExtractorTipoCambio(local_tmp_path / "tipo_cambio.csv")
    respaldo_vacio = pd.DataFrame(columns=["fecha", "compra", "venta"])

    monkeypatch.setattr(
        extractor,
        "_obtener_bloque_api",
        lambda inicio, fin: (_ for _ in ()).throw(RuntimeError("sin API")),
    )

    registros = extractor._resolver_bloque(
        datetime(2026, 1, 1),
        datetime(2026, 1, 3),
        respaldo_vacio,
    )

    assert len(registros) == 3
    assert all(registro.fuente_id == FUENTE_RESPALDO for registro in registros)


def test_tipo_cambio_historico_sobrescribe_csv_en_modo_historico(local_tmp_path) -> None:
    ruta_csv = local_tmp_path / "tipo_cambio.csv"
    pd.DataFrame([{"fecha": "2020-01-01", "compra": 1.0, "venta": 2.0}]).to_csv(
        ruta_csv, index=False
    )
    extractor = ExtractorTipoCambio(ruta_csv)
    extractor._guardar_registros_csv(
        [
            extractor._clonar_registro(
                extractor._simular_diario(),
                FUENTE_RESPALDO,
            )
        ],
        sobrescribir=True,
    )
    resultado = pd.read_csv(ruta_csv)

    assert "2020-01-01" not in set(resultado["fecha"].astype(str))


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
        "etl_dolar_canasta.extract.requests.get",
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
        "etl_dolar_canasta.extract.requests.get",
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
        "etl_dolar_canasta.extract.requests.get",
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


def test_tipo_cambio_falla_si_todas_las_fuentes_fallan(
    monkeypatch: pytest.MonkeyPatch, local_tmp_path
) -> None:
    extractor = ExtractorTipoCambio(local_tmp_path / "tipo_cambio.csv")

    monkeypatch.setattr(extractor, "_obtener_diario_api", lambda: (_ for _ in ()).throw(RuntimeError("api")))
    monkeypatch.setattr(extractor, "_obtener_diario_csv", lambda: (_ for _ in ()).throw(RuntimeError("csv")))
    monkeypatch.setattr(extractor, "_simular_diario", lambda: (_ for _ in ()).throw(RuntimeError("sim")))

    with pytest.raises(RuntimeError, match="tipo de cambio diario"):
        extractor.obtener_diario(guardar_csv=False)


def test_combustible_falla_si_todas_las_fuentes_fallan(
    monkeypatch: pytest.MonkeyPatch, local_tmp_path
) -> None:
    extractor = ExtractorCombustible(local_tmp_path / "combustible.csv")

    monkeypatch.setattr(extractor, "_obtener_api", lambda: (_ for _ in ()).throw(RuntimeError("api")))
    monkeypatch.setattr(extractor, "_leer_csv", lambda: (_ for _ in ()).throw(RuntimeError("csv")))
    monkeypatch.setattr(extractor, "_simular_registros", lambda: (_ for _ in ()).throw(RuntimeError("sim")))

    with pytest.raises(RuntimeError, match="historico de combustibles"):
        extractor.obtener(guardar_csv=False)
