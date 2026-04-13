from __future__ import annotations

from pathlib import Path

from test_runner import EjecutorPruebas


class DummyParametros:
    debe_ejecutar_pruebas_integrales = True
    debe_ejecutar_pruebas_etl = True
    debe_ejecutar_pruebas_dbconn = True
    server = "localhost"
    driver = "ODBC Driver 17 for SQL Server"
    trusted_connection = True
    username = None
    password = None


def test_runner_integral_ejecuta_core_etl_y_dbconn_en_orden(monkeypatch) -> None:
    llamadas: list[tuple[str, str]] = []

    def fake_pytest(self, etiqueta, descripcion, ruta, env=None):
        llamadas.append((etiqueta, str(ruta)))

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(EjecutorPruebas, "_ejecutar_pytest", fake_pytest)

    resultado = EjecutorPruebas(Path.cwd(), DummyParametros()).ejecutar()

    assert resultado == 0
    assert llamadas == [
        ("TEST-CORE", str(Path("tests") / "unit" / "core")),
        ("TEST-ETL", str(Path("tests") / "unit" / "etl_dolar")),
        ("TEST-ETL", str(Path("tests") / "unit" / "etl_combustible")),
        ("TEST-ETL", str(Path("tests") / "unit" / "etl_cba")),
        ("TEST-ETL", str(Path("tests") / "unit" / "etl_clima")),
        ("TEST-DBCONN", str(Path("tests") / "smoke")),
    ]
