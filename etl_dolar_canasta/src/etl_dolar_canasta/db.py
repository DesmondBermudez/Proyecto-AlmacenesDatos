from __future__ import annotations

from contextlib import contextmanager

from etl_dolar_canasta.config import ParametrosETL


class SqlServerDB:
    def __init__(self, parametros: ParametrosETL) -> None:
        self.parametros = parametros

    def conectar(self):
        import pyodbc

        return pyodbc.connect(self.parametros.cadena_conexion())

    @contextmanager
    def connection(self):
        conn = self.conectar()
        try:
            yield conn
        finally:
            conn.close()
