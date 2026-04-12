from __future__ import annotations

import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "etl" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app import ETLDolarCanastaApp
from cli import GestorCLI


def main() -> int:
    parametros = GestorCLI().parsear()
    return ETLDolarCanastaApp(parametros, BASE_DIR).ejecutar()


if __name__ == "__main__":
    raise SystemExit(main())
