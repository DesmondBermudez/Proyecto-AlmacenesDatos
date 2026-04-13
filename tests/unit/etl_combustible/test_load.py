from __future__ import annotations

from contextlib import contextmanager

from etl_combustible.load import CargadorCombustible
from etl_combustible.models import (
    FUENTE_RESPALDO,
    RegistroPrecioCombustible,
    RegistroProductoCombustible,
)


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


def test_cargar_combustibles_limpia_staging_y_respeta_fuente_id() -> None:
    fake_db = FakeDB()
    cargador = CargadorCombustible(fake_db)

    cargador.cargar_staging(
        [
            RegistroProductoCombustible(
                nombre_raw="Gasolina RON 95",
                nombre_normalizado="Gasolina RON 95",
                fuente_id=FUENTE_RESPALDO,
            )
        ],
        [
            RegistroPrecioCombustible(
                fecha_raw="2026-04-11T00:00:00",
                nombre_producto_raw="Gasolina RON 95",
                precio=780.0,
                fuente_id=FUENTE_RESPALDO,
            )
        ],
    )

    sql_texts = [sql for sql, _ in fake_db.connection_instance.cursor_instance.execute_calls]
    bulk_calls = fake_db.connection_instance.cursor_instance.executemany_calls

    assert any("DELETE FROM dbo.StagingPrecioGasolina" in sql for sql in sql_texts)
    assert any("DELETE FROM dbo.StagingProducto" in sql for sql in sql_texts)
    assert len(bulk_calls) == 3
    assert "INSERT INTO dbo.StagingProducto" in bulk_calls[0][0]
    assert "INSERT INTO dbo.StagingFecha" in bulk_calls[1][0]
    assert bulk_calls[1][1][0][2] == "2026-04-11"
    assert "INSERT INTO dbo.StagingPrecioGasolina" in bulk_calls[2][0]
    assert bulk_calls[2][1][0][-1] == FUENTE_RESPALDO
