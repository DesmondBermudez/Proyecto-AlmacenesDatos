from __future__ import annotations

from contextlib import contextmanager

import pandas as pd

from etl_clima.load import CargadorClima
from etl_clima.models import FUENTE_NASA


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


def test_cargador_clima_guarda_csv(local_tmp_path) -> None:
    ruta_salida = local_tmp_path / "clima.csv"
    cargador = CargadorClima(ruta_salida)

    resultado = cargador.guardar_csv(
        pd.DataFrame(
            [
                {
                    "zona": "MATINA",
                    "anio": 2024,
                    "mes": 1,
                }
            ]
        )
    )

    assert resultado == ruta_salida
    assert ruta_salida.exists()


def test_cargador_clima_puebla_staging_de_zonas_y_clima() -> None:
    fake_db = FakeDB()
    cargador = CargadorClima(db=fake_db)
    df = pd.DataFrame(
        [
            {
                "zona": "MATINA",
                "latitud": 10.0,
                "longitud": -83.35,
                "anio": 2024,
                "mes": 1,
                "temp_max": 30.5,
                "temp_min": 22.0,
                "precipitacion": 5.2,
                "humedad": 83.0,
                "radiacion_solar": 4.7,
            }
        ]
    )

    cargador.cargar_staging(df)

    sql_texts = [sql for sql, _ in fake_db.connection_instance.cursor_instance.execute_calls]
    lote = fake_db.connection_instance.cursor_instance.executemany_calls[0][1]

    assert any("DELETE FROM dbo.StagingClimaMensual" in sql for sql in sql_texts)
    assert any("INSERT INTO dbo.StagingZonaClimatica" in sql for sql in sql_texts)
    assert any("INSERT INTO dbo.StagingFecha" in sql for sql in sql_texts)
    assert lote[0][-1] == FUENTE_NASA
