from __future__ import annotations

from contextlib import contextmanager
from datetime import date

from etl_dolar.load import CargadorDolar
from etl_dolar.models import RegistroTipoCambio


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


def test_cargar_staging_dolar_inserta_fechas_y_registros_en_lotes() -> None:
    fake_db = FakeDB()
    cargador = CargadorDolar(fake_db)

    cargador.cargar_staging(
        [
            RegistroTipoCambio(fecha=date(2026, 4, 11), compra=500.0, venta=505.0),
            RegistroTipoCambio(fecha=date(2026, 4, 12), compra=501.0, venta=506.0),
        ]
    )

    bulk_calls = fake_db.connection_instance.cursor_instance.executemany_calls
    assert len(bulk_calls) == 2
    assert "INSERT INTO dbo.StagingFecha" in bulk_calls[0][0]
    assert "INSERT INTO dbo.StagingTipoCambio" in bulk_calls[1][0]
    assert bulk_calls[1][1][0] == ("2026-04-11", 20260411, 1, 2, 1, 500.0, 505.0, 502.5)
    assert bulk_calls[1][1][1] == ("2026-04-12", 20260412, 1, 2, 1, 501.0, 506.0, 503.5)
