from __future__ import annotations

from contextlib import contextmanager

import pandas as pd

from etl_dolar_canasta.load import CargadorDW
from etl_dolar_canasta.models import (
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

    def close(self) -> None:
        return None


class FakeDB:
    def __init__(self) -> None:
        self.connection_instance = FakeConnection()

    @contextmanager
    def connection(self):
        yield self.connection_instance


def test_limpiar_staging_borra_tablas_transitorias_en_orden_seguro() -> None:
    fake_db = FakeDB()
    cargador = CargadorDW(fake_db)

    cargador.limpiar_staging()

    execs = [sql.strip() for sql, _ in fake_db.connection_instance.cursor_instance.execute_calls]

    assert execs == [
        "DELETE FROM dbo.StagingClimaMensual",
        "DELETE FROM dbo.StagingZonaClimatica",
        "DELETE FROM dbo.StagingHistoricoCanasta",
        "DELETE FROM dbo.StagingPrecioGasolina",
        "DELETE FROM dbo.StagingProducto",
        "DELETE FROM dbo.StagingTipoCambio",
        "DELETE FROM dbo.StagingFecha",
    ]


def test_cargar_canasta_inserta_staging_fecha_con_parametros_alineados() -> None:
    fake_db = FakeDB()
    cargador = CargadorDW(fake_db)
    df = pd.DataFrame(
        [
            {
                "Fecha": "2026-04-01",
                "NombreProducto": "ARROZ",
                "Categoria": "CEREALES",
                "EsImportado": 0,
                "UnidadMedida": "KG",
                "Provincia": "SAN JOSE",
                "Canton": "CENTRAL",
                "Distrito": "CARMEN",
                "PrecioColones": 820.5,
                "PrecioBaseReferencia": 800.0,
                "FactorCanasta": 1.02,
            }
        ]
    )

    cargador.cargar_canasta(df)

    fecha_calls = [
        params
        for sql, params in fake_db.connection_instance.cursor_instance.execute_calls
        if "INSERT INTO dbo.StagingFecha" in sql
    ]

    assert len(fecha_calls) == 1
    assert len(fecha_calls[0]) == 8
    assert fecha_calls[0][0] == 20260401
    assert fecha_calls[0][1] == 20260401
    assert fecha_calls[0][2] == "2026-04-01"


def test_cargar_combustibles_limpia_staging_y_respeta_fuente_id() -> None:
    fake_db = FakeDB()
    cargador = CargadorDW(fake_db)

    cargador.cargar_combustibles(
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
    insert_params = [
        params
        for sql, params in fake_db.connection_instance.cursor_instance.execute_calls
        if "INSERT INTO dbo.StagingPrecioGasolina" in sql
    ]
    fecha_calls = [
        params
        for sql, params in fake_db.connection_instance.cursor_instance.execute_calls
        if "INSERT INTO dbo.StagingFecha" in sql
    ]

    assert any("DELETE FROM dbo.StagingPrecioGasolina" in sql for sql in sql_texts)
    assert any("DELETE FROM dbo.StagingProducto" in sql for sql in sql_texts)
    assert len(fecha_calls) == 1
    assert fecha_calls[0][2] == "2026-04-11"
    assert insert_params[0][-1] == FUENTE_RESPALDO


def test_ejecutar_transformaciones_dw_respeta_orden_actual() -> None:
    fake_db = FakeDB()
    cargador = CargadorDW(fake_db)

    cargador.ejecutar_transformaciones_dw()

    execs = [sql.strip() for sql, _ in fake_db.connection_instance.cursor_instance.execute_calls]

    assert execs == [
        "EXEC dbo.sp_Transform_DimFecha",
        "EXEC dbo.sp_Transform_DimProducto",
        "EXEC dbo.sp_Transform_DimRegion",
        "EXEC dbo.sp_Transform_DimZonaClimatica",
        "EXEC dbo.sp_Transform_FactTipoCambio",
        "EXEC dbo.sp_Load_FactPrecioCombustible",
        "EXEC dbo.sp_Load_FactPreciosCanasta",
        "EXEC dbo.sp_Load_FactClimaMensual",
    ]
