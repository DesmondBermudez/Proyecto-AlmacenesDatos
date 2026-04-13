from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from admin_db_conn.config import ParametrosETL
from runtime import formatear_duracion


class EjecutorPruebas:
    RUTA_PRUEBA_CORE = Path("tests") / "unit" / "core"
    RUTAS_PRUEBA_ETL = {
        "dolar": Path("tests") / "unit" / "etl_dolar",
        "combustible": Path("tests") / "unit" / "etl_combustible",
        "cba": Path("tests") / "unit" / "etl_cba",
        "clima": Path("tests") / "unit" / "etl_clima",
    }
    RUTA_PRUEBA_DBCONN = Path("tests") / "smoke"

    def __init__(self, base_dir: Path, parametros: ParametrosETL) -> None:
        self.base_dir = base_dir
        self.parametros = parametros
        self._inicio = 0.0

    def ejecutar(self) -> int:
        self._inicio = time.perf_counter()
        self._imprimir_encabezado()
        if self.parametros.debe_ejecutar_pruebas_integrales:
            resultado = self._ejecutar_pytest("TEST-CORE", "pruebas generales", self.RUTA_PRUEBA_CORE)
            if resultado.returncode != 0:
                return resultado.returncode
            resultado = self._ejecutar_pruebas_etl(("dolar", "combustible", "cba", "clima"))
            if resultado != 0:
                return resultado
            resultado = self._ejecutar_prueba_dbconn()
            if resultado != 0:
                return resultado
            self._imprimir_resumen_pruebas()
            return 0

        if self.parametros.debe_ejecutar_pruebas_etl:
            resultado = self._ejecutar_pruebas_etl(self.parametros.objetivos_prueba_etl)
            if resultado != 0:
                return resultado

        if self.parametros.debe_ejecutar_pruebas_dbconn:
            resultado = self._ejecutar_prueba_dbconn()
            if resultado != 0:
                return resultado

        self._imprimir_resumen_pruebas()
        return 0

    def _imprimir_encabezado(self) -> None:
        print("=" * 50, flush=True)
        print("VALIDACION PREVIA DEL PROYECTO", flush=True)
        print("=" * 50, flush=True)

    def _ejecutar_pruebas_etl(self, objetivos: tuple[str, ...]) -> int:
        for objetivo in objetivos:
            ruta = self.RUTAS_PRUEBA_ETL[objetivo]
            resultado = self._ejecutar_pytest("TEST-ETL", f"pruebas de {objetivo}", ruta)
            if resultado.returncode != 0:
                return resultado.returncode
        return 0

    def _ejecutar_prueba_dbconn(self) -> int:
        env = os.environ.copy()
        env["ETL_SMOKE_SQL"] = "1"
        env["ETL_SQL_SERVER"] = self.parametros.server
        env["ETL_SQL_DRIVER"] = self.parametros.driver
        env["ETL_SQL_TRUSTED_CONNECTION"] = "1" if self.parametros.trusted_connection else "0"
        if self.parametros.username:
            env["ETL_SQL_USERNAME"] = self.parametros.username
        if self.parametros.password:
            env["ETL_SQL_PASSWORD"] = self.parametros.password

        resultado = self._ejecutar_pytest(
            "TEST-DBCONN",
            "pruebas de conexion",
            self.RUTA_PRUEBA_DBCONN,
            env=env,
        )
        return resultado.returncode

    def _ejecutar_pytest(
        self,
        etiqueta: str,
        descripcion: str,
        ruta: Path,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess:
        print(f"[{etiqueta}] Ejecutando {descripcion}: {ruta}", flush=True)
        inicio_bloque = time.perf_counter()
        resultado = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", str(ruta)],
            cwd=self.base_dir,
            check=False,
            env=env or os.environ.copy(),
        )
        duracion = time.perf_counter() - inicio_bloque
        acumulado = time.perf_counter() - self._inicio
        estado = "OK" if resultado.returncode == 0 else f"ERROR ({resultado.returncode})"
        print(
            f"[{etiqueta}] Finalizado {descripcion}: {estado} | "
            f"Bloque: {formatear_duracion(duracion)} | "
            f"Acumulado pruebas: {formatear_duracion(acumulado)}",
            flush=True,
        )
        return resultado

    def _imprimir_resumen_pruebas(self) -> None:
        if self._inicio == 0.0:
            return
        print(
            f"[TEST] Tiempo total pruebas: "
            f"{formatear_duracion(time.perf_counter() - self._inicio)}",
            flush=True,
        )
