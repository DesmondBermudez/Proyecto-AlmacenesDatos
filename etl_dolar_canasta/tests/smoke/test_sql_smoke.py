from __future__ import annotations

import os
import uuid
from pathlib import Path

import pandas as pd
import pytest

from etl_dolar_canasta.config import ParametrosETL
from etl_dolar_canasta.db import SqlServerDB
from etl_dolar_canasta.load import CargadorDW
from etl_dolar_canasta.models import RegistroTipoCambio


pytestmark = pytest.mark.smoke_sql


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


def test_sql_smoke_carga_staging_y_procedimientos() -> None:
    if os.getenv("ETL_SMOKE_SQL") != "1":
        pytest.skip("Smoke SQL deshabilitado")

    script_path = Path(__file__).resolve().parents[3] / "dw_database" / "01 - DW_Canasta.sql"
    database_name = f"DW_Dolar_Canasta_Smoke_{uuid.uuid4().hex[:8]}"
    master_db = SqlServerDB(_build_params("master"))
    smoke_db = SqlServerDB(_build_params(database_name))

    with master_db.connection() as conn:
        cursor = conn.cursor()
        script = script_path.read_text(encoding="utf-8").replace("DW_Dolar_Canasta", database_name)
        for lote in _split_sql_batches(script):
            cursor.execute(lote)
        conn.commit()

    try:
        cargador = CargadorDW(smoke_db)
        cargador.asegurar_catalogos_base()
        cargador.cargar_tipo_cambio(
            [
                RegistroTipoCambio(
                    fecha=pd.Timestamp("2026-04-11").date(),
                    compra=500.0,
                    venta=505.0,
                )
            ]
        )
        cargador.cargar_canasta(
            pd.DataFrame(
                [
                    {
                        "Fecha": "2026-04-01",
                        "NombreProducto": "ARROZ GRANO ENTERO 80%",
                        "Categoria": "CEREALES",
                        "EsImportado": 0,
                        "UnidadMedida": "KILOGRAMO",
                        "Provincia": "SAN JOSE",
                        "Canton": "SAN JOSE",
                        "Distrito": "CARMEN",
                        "PrecioColones": 820.0,
                        "PrecioBaseReferencia": 800.0,
                        "FactorCanasta": 1.0,
                    }
                ]
            )
        )
        cargador.ejecutar_transformaciones_dw()

        with smoke_db.connection() as conn:
            cursor = conn.cursor()
            counts = {}
            for tabla in (
                "DimFecha",
                "DimProducto",
                "DimRegion",
                "FactTipoCambio",
                "FactPreciosCanasta",
            ):
                cursor.execute(f"SELECT COUNT(*) FROM dbo.{tabla}")
                counts[tabla] = cursor.fetchone()[0]

        assert all(valor > 0 for valor in counts.values())
    finally:
        with master_db.connection() as conn:
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
            conn.commit()
