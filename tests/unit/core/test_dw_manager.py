from __future__ import annotations

from contextlib import contextmanager

from dw_manager import CoordinadorDW


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


def test_limpiar_staging_borra_tablas_transitorias_en_orden_seguro() -> None:
    fake_db = FakeDB()
    coordinador = CoordinadorDW(fake_db)

    coordinador.limpiar_staging()

    execs = [sql.strip() for sql, _ in fake_db.connection_instance.cursor_instance.execute_calls]

    assert execs == [
        "DELETE FROM dbo.StagingClimaMensual",
        "DELETE FROM dbo.StagingZonaClimatica",
        "DELETE FROM dbo.StagingInec",
        "DELETE FROM dbo.StagingPrecioGasolina",
        "DELETE FROM dbo.StagingProducto",
        "DELETE FROM dbo.StagingTipoCambio",
        "DELETE FROM dbo.StagingFecha",
    ]


def test_asegurar_catalogos_base_registra_fuentes_y_monedas_vigentes() -> None:
    fake_db = FakeDB()
    coordinador = CoordinadorDW(fake_db)

    coordinador.asegurar_catalogos_base()

    params = [params for _, params in fake_db.connection_instance.cursor_instance.execute_calls]
    assert (1, 1, "Ministerio de Hacienda CR", "MHCR") in params
    assert (5, 5, "INEC", "INEC") in params
    assert (1, 1, "Dolar Americano", "USD") in params
    assert (2, 2, "Colon Costarricense", "CRC") in params


def test_ejecutar_transformaciones_dw_respeta_nuevo_orden_por_etl() -> None:
    fake_db = FakeDB()
    coordinador = CoordinadorDW(fake_db)

    coordinador.ejecutar_transformaciones_dw()

    execs = [sql.strip() for sql, _ in fake_db.connection_instance.cursor_instance.execute_calls]

    assert execs == [
        "EXEC dbo.sp_Transform_DimFecha",
        "EXEC dbo.sp_Transform_DimProducto",
        "EXEC dbo.sp_Transform_DimZonaCBA",
        "EXEC dbo.sp_Transform_DimCategoriaCBA",
        "EXEC dbo.sp_Transform_DimZonaClimatica",
        "EXEC dbo.sp_Transform_FactTipoCambio",
        "EXEC dbo.sp_Load_FactPrecioCombustible",
        "EXEC dbo.sp_Load_FactCanastaInecOficial",
        "EXEC dbo.sp_Load_FactClimaMensual",
    ]
