from __future__ import annotations

import sys
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "etl" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app import ETLApp
from cli import GestorCLI
from runtime import formatear_duracion
from test_runner import EjecutorPruebas


def _imprimir_aviso_only_test_si_aplica(parametros) -> None:
    if parametros.debe_ejecutar_solo_pruebas and parametros.modo_carga_indicado:
        print("##############################################")
        print("!!! Aviso: --only-test invalida --modo-carga !!!")
        print("##############################################")


def main() -> int:
    inicio_total = time.perf_counter()
    parametros = GestorCLI().parsear()
    _imprimir_aviso_only_test_si_aplica(parametros)
    try:
        if parametros.debe_ejecutar_pruebas:
            resultado_pruebas = EjecutorPruebas(BASE_DIR, parametros).ejecutar()
            if resultado_pruebas != 0:
                return resultado_pruebas
            if parametros.debe_ejecutar_solo_pruebas:
                return 0
        return ETLApp(parametros, BASE_DIR).ejecutar()
    finally:
        print("=" * 50)
        print(f"TIEMPO TOTAL DE EJECUCION: {formatear_duracion(time.perf_counter() - inicio_total)}")
        print("=" * 50)


if __name__ == "__main__":
    raise SystemExit(main())
