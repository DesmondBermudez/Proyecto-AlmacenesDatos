from __future__ import annotations

from contextlib import contextmanager
from datetime import date

from etl_dolar.load import CargadorDolar
from etl_dolar.models import RegistroTipoCambio


class FakeCursor:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, tuple | None]] = []

    def execute(self, sql: str, params: tuple | None = None) -> None:
        self.execute_calls.append((sql, params))


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


def test_cargar_staging_dolar_ejecuta_procedimiento_por_registro() -> None:
    fake_db = FakeDB()
    cargador = CargadorDolar(fake_db)

    cargador.cargar_staging(
        [
            RegistroTipoCambio(fecha=date(2026, 4, 11), compra=500.0, venta=505.0),
            RegistroTipoCambio(fecha=date(2026, 4, 12), compra=501.0, venta=506.0),
        ]
    )

    calls = fake_db.connection_instance.cursor_instance.execute_calls
    assert len(calls) == 2
    assert all("sp_InsertarTipoCambioStaging" in sql for sql, _ in calls)
    assert calls[0][1] == ("2026-04-11", 500.0, 505.0, 1, 2, 1)
    assert calls[1][1] == ("2026-04-12", 501.0, 506.0, 1, 2, 1)
