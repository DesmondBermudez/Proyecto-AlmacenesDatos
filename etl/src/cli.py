from __future__ import annotations

import argparse
import sys

from admin_db_conn.config import ParametrosETL


class GestorCLI:
    def __init__(self) -> None:
        self.parser = argparse.ArgumentParser(
            prog="ETL.py",
            description=(
                "ETL para dolar, combustibles, CBA oficial del INEC y clima.\n"
                "Extrae datos desde APIs, respaldos CSV, archivos oficiales XLSX y simulacion controlada,\n"
                "puebla staging en SQL Server y luego carga el DW mediante procedimientos almacenados."
            ),
            epilog=(
                "Ejemplos de uso:\n"
                "  python ETL.py\n"
                "  python ETL.py --modo-carga direct-insert\n"
                "  python ETL.py --modo-carga historico\n"
                "  python ETL.py --modo-carga historico --no-generar-historicos\n"
                "  python ETL.py --test\n"
                "  python ETL.py --test --only-test\n"
                "  python ETL.py --test-ETL\n"
                "  python ETL.py --test-ETL cba\n"
                "  python ETL.py --test-ETL dolar combustible clima --test-DBconn\n"
                "  python ETL.py --test-DBconn --only-test\n"
                "  python ETL.py --server .\\SQLEXPRESS --trusted-connection\n"
                "  python ETL.py --server localhost --database DW_Dolar_Canasta "
                "--username sa --password secreto --no-trusted-connection"
            ),
            formatter_class=argparse.RawTextHelpFormatter,
        )
        self._configurar()

    def _configurar(self) -> None:
        self.parser.add_argument(
            "--server",
            default="localhost",
            help="Servidor o instancia de SQL Server.\nDefault: localhost",
        )
        self.parser.add_argument(
            "--database",
            default="DW_Dolar_Canasta",
            help="Base de datos destino del Data Warehouse.\nDefault: DW_Dolar_Canasta",
        )
        self.parser.add_argument(
            "--driver",
            default="ODBC Driver 17 for SQL Server",
            help="Driver ODBC para la conexion.\nDefault: ODBC Driver 17 for SQL Server",
        )
        self.parser.add_argument(
            "--username",
            help="Usuario SQL Server para autenticacion por credenciales.",
        )
        self.parser.add_argument(
            "--password",
            help="Contrasena del usuario SQL Server.",
        )
        self.parser.add_argument(
            "--trusted-connection",
            dest="trusted_connection",
            action="store_true",
            default=True,
            help=(
                "Usa autenticacion integrada de Windows.\n"
                "Default: activado cuando no se envian credenciales SQL."
            ),
        )
        self.parser.add_argument(
            "--no-trusted-connection",
            dest="trusted_connection",
            action="store_false",
            help="Desactiva la autenticacion integrada.",
        )
        self.parser.add_argument(
            "--modo-carga",
            choices=("direct-insert", "historico"),
            default="direct-insert",
            help=(
                "Modo de ejecucion del ETL.\n"
                "  direct-insert : procesa el dolar diario y ejecuta el resto del flujo\n"
                "                  con el alcance actual de cada dominio.\n"
                "  historico     : regenera historicos desde la fuente principal cuando es posible\n"
                "                  y luego carga staging y DW."
            ),
        )
        self.parser.add_argument(
            "--generar-historicos",
            dest="generar_historicos",
            action="store_true",
            default=True,
            help=(
                "Actualiza o genera los CSV operativos de respaldo antes de poblar staging.\n"
                "Aplica al historico de dolar, combustibles y clima.\n"
                "La CBA oficial usa archivos XLSX desde etl/data/raw/cba.\n"
                "Default: activado."
            ),
        )
        self.parser.add_argument(
            "--no-generar-historicos",
            dest="generar_historicos",
            action="store_false",
            help="No regenera los CSV operativos y reutiliza los respaldos existentes cuando el flujo lo permite.",
        )
        self.parser.add_argument(
            "--test",
            action="store_true",
            help=(
                "Ejecuta la prueba integral de la solucion.\n"
                "Corre primero pruebas ETL y DB connection; si pasan y no se uso --only-test,\n"
                "continua al flujo real."
            ),
        )
        self.parser.add_argument(
            "--test-ETL",
            dest="test_etl",
            nargs="*",
            choices=("all", "dolar", "combustible", "cba", "clima"),
            help=(
                "Ejecuta pruebas aisladas de ETL.\n"
                "Si se invoca sin valores o con 'all', prueba todos los ETLs.\n"
                "Puede combinarse con --test-DBconn cuando no se use --test."
            ),
        )
        self.parser.add_argument(
            "--test-DBconn",
            dest="test_dbconn",
            action="store_true",
            help=(
                "Ejecuta pruebas de conexion y BD dummy.\n"
                "Si pasan y no se uso --only-test, el flujo real continua con la misma configuracion."
            ),
        )
        self.parser.add_argument(
            "--only-test",
            action="store_true",
            help=(
                "Ejecuta solo las pruebas indicadas y no continua al flujo real del ETL.\n"
                "Requiere usar --test, --test-ETL y/o --test-DBconn.\n"
                "Si se combina con --modo-carga, el modo se ignora para esa ejecucion."
            ),
        )

    def parsear(self, args: list[str] | None = None) -> ParametrosETL:
        raw_args = list(sys.argv[1:] if args is None else args)
        ns = self.parser.parse_args(args=args)
        if ns.test and (ns.test_etl is not None or ns.test_dbconn):
            self.parser.error("--test no puede combinarse con --test-ETL ni --test-DBconn")
        if ns.only_test and not (ns.test or ns.test_etl is not None or ns.test_dbconn):
            self.parser.error("--only-test requiere --test, --test-ETL o --test-DBconn")

        return ParametrosETL(
            server=ns.server,
            database=ns.database,
            driver=ns.driver,
            username=ns.username,
            password=ns.password,
            trusted_connection=ns.trusted_connection,
            modo_carga=ns.modo_carga,
            generar_historicos=ns.generar_historicos,
            test_full_enabled=ns.test,
            test_etl_targets=None if ns.test_etl is None else tuple(ns.test_etl),
            test_dbconn_enabled=ns.test_dbconn,
            only_test_enabled=ns.only_test,
            modo_carga_indicado="--modo-carga" in raw_args,
        )
