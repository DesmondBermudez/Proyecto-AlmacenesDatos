from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pandas as pd
import pytest

from admin_db_conn.config import ParametrosETL
from admin_db_conn.db import SqlServerDB
from dw_manager import CoordinadorDW
from etl_cba.load import CargadorCBA
from etl_clima.load import CargadorClima
from etl_combustible.load import CargadorCombustible
from etl_combustible.models import RegistroPrecioCombustible, RegistroProductoCombustible
from etl_dolar.load import CargadorDolar
from etl_dolar.models import RegistroTipoCambio


pytestmark = pytest.mark.smoke_sql


def _is_azure_sql_server(server: str) -> bool:
    servidor = server.strip().lower().split(",", maxsplit=1)[0]
    return servidor.endswith(".database.windows.net")


def _quote_sql_identifier(identifier: str) -> str:
    return f"[{identifier.replace(']', ']]')}]"


def _split_sql_batches(script: str) -> list[str]:
    lotes: list[str] = []
    actual: list[str] = []
    for linea in script.splitlines():
        if linea.strip().upper() == "GO":
            lote = "\n".join(actual).strip()
            if lote:
                lotes.append(lote)
            actual = []
            continue
        actual.append(linea)
    lote_final = "\n".join(actual).strip()
    if lote_final:
        lotes.append(lote_final)
    return lotes


def _bool_from_env(nombre: str, default: bool = True) -> bool:
    valor = os.getenv(nombre)
    if valor is None:
        return default
    return valor.lower() in {"1", "true", "yes", "on"}


def _build_params(database: str) -> ParametrosETL:
    return ParametrosETL(
        server=os.getenv("ETL_SQL_SERVER", "localhost"),
        database=database,
        driver=os.getenv("ETL_SQL_DRIVER", "ODBC Driver 17 for SQL Server"),
        username=os.getenv("ETL_SQL_USERNAME"),
        password=os.getenv("ETL_SQL_PASSWORD"),
        trusted_connection=_bool_from_env("ETL_SQL_TRUSTED_CONNECTION", default=True),
    )


def _build_dw_script_path(server: str) -> Path:
    script_name = (
        "02 - DW_Canasta_AzureSQL.sql"
        if _is_azure_sql_server(server)
        else "01 - DW_Canasta.sql"
    )
    return Path(__file__).resolve().parents[2] / "dw_database" / script_name


def _create_smoke_database(master_db: SqlServerDB, database_name: str) -> None:
    nombre_literal = database_name.replace("'", "''")
    nombre_identificador = _quote_sql_identifier(database_name)
    conn = master_db.conectar()
    conn.autocommit = True
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            IF DB_ID('{nombre_literal}') IS NULL
            BEGIN
                CREATE DATABASE {nombre_identificador};
            END
            """
        )
    finally:
        conn.close()


def _wait_until_database_is_ready(
    smoke_db: SqlServerDB, *, retries: int = 15, delay_seconds: float = 2.0
) -> None:
    ultimo_error: Exception | None = None
    for intento in range(retries):
        try:
            conn = smoke_db.conectar()
            conn.close()
            return
        except Exception as exc:  # pragma: no cover - depende del motor SQL real
            ultimo_error = exc
            if intento == retries - 1:
                raise
            time.sleep(delay_seconds)
    if ultimo_error is not None:  # pragma: no cover - salida defensiva
        raise ultimo_error


def _cleanup_orphan_smoke_databases(master_db: SqlServerDB) -> None:
    conn = master_db.conectar()
    conn.autocommit = True
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name
            FROM sys.databases
            WHERE name LIKE 'DW_Dolar_Canasta_Smoke[_]%'
            """
        )
        nombres = [fila[0] for fila in cursor.fetchall()]
        for nombre in nombres:
            nombre_literal = nombre.replace("'", "''")
            nombre_identificador = _quote_sql_identifier(nombre)
            cursor.execute(
                f"""
                IF DB_ID('{nombre_literal}') IS NOT NULL
                BEGIN
                    ALTER DATABASE {nombre_identificador} SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
                    DROP DATABASE {nombre_identificador};
                END
                """
            )
    finally:
        conn.close()


def test_sql_smoke_carga_staging_y_procedimientos() -> None:
    if os.getenv("ETL_SMOKE_SQL") != "1":
        pytest.skip("Smoke SQL deshabilitado")

    database_name = f"DW_Dolar_Canasta_Smoke_{uuid.uuid4().hex[:8]}"
    master_db = SqlServerDB(_build_params("master"))
    smoke_db = SqlServerDB(_build_params(database_name))
    script_path = _build_dw_script_path(master_db.parametros.server)
    _cleanup_orphan_smoke_databases(master_db)

    if _is_azure_sql_server(master_db.parametros.server):
        _create_smoke_database(master_db, database_name)
        _wait_until_database_is_ready(smoke_db)
        conn = smoke_db.conectar()
    else:
        conn = master_db.conectar()

    conn.autocommit = True
    try:
        cursor = conn.cursor()
        script = script_path.read_text(encoding="utf-8-sig").replace(
            "DW_Dolar_Canasta", database_name
        )
        for lote in _split_sql_batches(script):
            cursor.execute(lote)
    finally:
        conn.close()

    try:
        coordinador = CoordinadorDW(smoke_db)
        coordinador.asegurar_catalogos_base()
        CargadorDolar(smoke_db).cargar_staging(
            [
                RegistroTipoCambio(
                    fecha=pd.Timestamp("2026-04-11").date(),
                    compra=500.0,
                    venta=505.0,
                )
            ]
        )
        CargadorCombustible(smoke_db).cargar_staging(
            [
                RegistroProductoCombustible(
                    nombre_raw="Gasolina RON 95",
                    nombre_normalizado="Gasolina RON 95",
                )
            ],
            [
                RegistroPrecioCombustible(
                    fecha_raw="2026-04-11T00:00:00",
                    nombre_producto_raw="Gasolina RON 95",
                    precio=780.0,
                )
            ],
        )
        CargadorCBA(smoke_db).cargar_staging(
            pd.DataFrame(
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
                    }
                ]
            )
        )
        CargadorClima(db=smoke_db).cargar_staging(
            pd.DataFrame(
                [
                    {
                        "zona": "MATINA",
                        "latitud": 10.0,
                        "longitud": -83.35,
                        "anio": 2026,
                        "mes": 4,
                        "temp_max": 30.5,
                        "temp_min": 22.1,
                        "precipitacion": 5.0,
                        "humedad": 84.0,
                        "radiacion_solar": 4.8,
                    }
                ]
            )
        )
        coordinador.ejecutar_transformaciones_dw()

        with smoke_db.connection() as conn:
            cursor = conn.cursor()
            counts = {}
            for tabla in (
                "DimFecha",
                "DimProducto",
                "DimZonaCBA",
                "DimCategoriaCBA",
                "DimZonaClimatica",
                "FactTipoCambio",
                "FactPrecioCombustible",
                "FactCanastaInecOficial",
                "FactClimaMensual",
            ):
                cursor.execute(f"SELECT COUNT(*) FROM dbo.{tabla}")
                counts[tabla] = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM dbo.StagingClimaMensual WHERE Precipitacion IS NOT NULL"
            )
            staging_precipitacion = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM dbo.FactClimaMensual WHERE Precipitacion IS NOT NULL"
            )
            dw_precipitacion = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM dbo.StagingTipoCambio "
                "WHERE TipoCambioCompra IS NOT NULL AND TipoCambioVenta IS NOT NULL"
            )
            staging_tipo_cambio = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM dbo.FactTipoCambio "
                "WHERE TipoCambioCompra IS NOT NULL AND TipoCambioVenta IS NOT NULL"
            )
            dw_tipo_cambio = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM dbo.StagingInec WHERE CostoPerCapita IS NOT NULL")
            staging_cba = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM dbo.FactCanastaInecOficial WHERE CostoPerCapita IS NOT NULL"
            )
            dw_cba = cursor.fetchone()[0]

        assert all(valor > 0 for valor in counts.values())
        assert staging_precipitacion > 0
        assert dw_precipitacion == staging_precipitacion
        assert staging_tipo_cambio > 0
        assert dw_tipo_cambio == staging_tipo_cambio
        assert staging_cba > 0
        assert dw_cba == staging_cba
    finally:
        conn = master_db.conectar()
        conn.autocommit = True
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                IF DB_ID('{database_name}') IS NOT NULL
                BEGIN
                    ALTER DATABASE [{database_name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
                    DROP DATABASE [{database_name}];
                END
                """
            )
        finally:
            conn.close()
