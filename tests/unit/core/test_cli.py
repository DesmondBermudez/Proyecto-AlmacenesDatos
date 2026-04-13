from __future__ import annotations

import pytest

from cli import GestorCLI


def test_cli_sin_parametros_de_prueba_no_activa_validaciones() -> None:
    parametros = GestorCLI().parsear([])

    assert not parametros.debe_ejecutar_pruebas
    assert not parametros.test_full_enabled
    assert parametros.test_etl_targets is None
    assert not parametros.test_dbconn_enabled
    assert not parametros.only_test_enabled
    assert not parametros.modo_carga_indicado


def test_cli_test_integral_activa_pruebas_completas() -> None:
    parametros = GestorCLI().parsear(["--test"])

    assert parametros.test_full_enabled
    assert parametros.debe_ejecutar_pruebas_integrales
    assert parametros.debe_ejecutar_pruebas_etl
    assert parametros.debe_ejecutar_pruebas_dbconn


def test_cli_test_etl_sin_objetivos_prueba_todos_los_etls() -> None:
    parametros = GestorCLI().parsear(["--test-ETL"])

    assert parametros.objetivos_prueba_etl == ("dolar", "combustible", "cba", "clima")
    assert parametros.debe_ejecutar_pruebas_etl
    assert not parametros.debe_ejecutar_pruebas_dbconn


def test_cli_test_etl_permite_objetivos_especificos() -> None:
    parametros = GestorCLI().parsear(["--test-ETL", "combustible", "clima"])

    assert parametros.objetivos_prueba_etl == ("combustible", "clima")


def test_cli_test_dbconn_activa_prueba_aislada() -> None:
    parametros = GestorCLI().parsear(["--test-DBconn"])

    assert parametros.test_dbconn_enabled
    assert parametros.debe_ejecutar_pruebas_dbconn


def test_cli_only_test_activa_ejecucion_solo_pruebas() -> None:
    parametros = GestorCLI().parsear(["--test-ETL", "clima", "--only-test"])

    assert parametros.only_test_enabled
    assert parametros.debe_ejecutar_solo_pruebas


def test_cli_rechaza_test_integral_combinado_con_pruebas_aisladas() -> None:
    with pytest.raises(SystemExit):
        GestorCLI().parsear(["--test", "--test-DBconn"])


def test_cli_rechaza_only_test_sin_parametros_de_prueba() -> None:
    with pytest.raises(SystemExit):
        GestorCLI().parsear(["--only-test"])


def test_cli_registra_modo_carga_cuando_only_test_esta_activo() -> None:
    parametros = GestorCLI().parsear(["--test", "--only-test", "--modo-carga", "historico"])

    assert parametros.only_test_enabled
    assert parametros.modo_carga_indicado
