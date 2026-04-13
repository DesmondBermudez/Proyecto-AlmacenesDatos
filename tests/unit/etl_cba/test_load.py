from __future__ import annotations

from contextlib import contextmanager

import pandas as pd

from etl_cba.load import CargadorCBA


class FakeCursor:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, tuple | None]] = []
        self.executemany_calls: list[tuple[str, list[tuple]]] = []
        self.fast_executemany = False

    def execute(self, sql: str, params: tuple | None = None) -> None:
        self.execute_calls.append((sql, params))

    def executemany(self, sql: str, params: list[tuple]) -> None:
        self.executemany_calls.append((sql, list(params)))


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()
        self.commit_count = 0

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.commit_count += 1


class FakeDB:
    def __init__(self) -> None:
        self.connection_instance = FakeConnection()

    @contextmanager
    def connection(self):
        yield self.connection_instance


def test_cargar_staging_cba_deduplica_e_inserta_staging_fecha_y_staging_inec() -> None:
    fake_db = FakeDB()
    cargador = CargadorCBA(fake_db)
    df = pd.DataFrame(
        [
            {
                "Fecha": "2026-04-01",
                "FechaID": 20260401,
                "Zona": "Nacional",
                "CategoriaNombre": "CBA",
                "PeriodoTextoOriginal": "abr-26",
                "CostoPerCapita": 65000.0,
                "ArchivoOrigen": "CBANacional_2011X2026XMESyProducto.xlsx",
                "FuenteID": 5,
            },
            {
                "Fecha": "2026-04-01",
                "FechaID": 20260401,
                "Zona": "Nacional",
                "CategoriaNombre": "CBA",
                "PeriodoTextoOriginal": "abr-26",
                "CostoPerCapita": 65000.0,
                "ArchivoOrigen": "CBANacional_2011X2026XMESyProducto.xlsx",
                "FuenteID": 5,
            },
        ]
    )

    cargador.cargar_staging(df)

    execs = fake_db.connection_instance.cursor_instance.execute_calls
    bulk = fake_db.connection_instance.cursor_instance.executemany_calls

    assert any(sql.strip() == "DELETE FROM dbo.StagingInec" for sql, _ in execs)
    fecha_calls = [params for sql, params in execs if "INSERT INTO dbo.StagingFecha" in sql]
    assert len(fecha_calls) == 1
    assert fecha_calls[0][0] == 20260401
    assert len(bulk) == 1
    assert "INSERT INTO dbo.StagingInec" in bulk[0][0]
    assert len(bulk[0][1]) == 1
