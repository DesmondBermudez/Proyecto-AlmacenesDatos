from __future__ import annotations

import argparse

from etl_dolar_canasta.config import ParametrosETL


class GestorCLI:
    def __init__(self) -> None:
        self.parser = argparse.ArgumentParser(
            prog="ETL_dolar_canasta.py",
            description=(
                "ETL para tipo de cambio, combustibles y canasta basica.\n"
                "Extrae datos, usa respaldos CSV cuando es necesario y carga el DW."
            ),
            epilog=(
                "Ejemplos de uso:\n"
                "  python ETL_dolar_canasta.py\n"
                "  python ETL_dolar_canasta.py --modo-carga historico\n"
                "  python ETL_dolar_canasta.py --server .\\SQLEXPRESS --trusted-connection\n"
                "  python ETL_dolar_canasta.py --server localhost --database DW_Dolar_Canasta "
                "--username sa --password secreto\n"
                "  python ETL_dolar_canasta.py --no-generar-historicos"
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
                "  direct-insert : consume el tipo de cambio actual y carga el DW.\n"
                "  historico     : recorre el historico del tipo de cambio desde 2000."
            ),
        )
        self.parser.add_argument(
            "--generar-historicos",
            dest="generar_historicos",
            action="store_true",
            default=True,
            help=(
                "Actualiza o genera los CSV historicos de tipo de cambio y combustibles.\n"
                "Default: activado."
            ),
        )
        self.parser.add_argument(
            "--no-generar-historicos",
            dest="generar_historicos",
            action="store_false",
            help="Desactiva la actualizacion de los CSV historicos y usa respaldos existentes.",
        )

    def parsear(self, args: list[str] | None = None) -> ParametrosETL:
        ns = self.parser.parse_args(args=args)
        return ParametrosETL(
            server=ns.server,
            database=ns.database,
            driver=ns.driver,
            username=ns.username,
            password=ns.password,
            trusted_connection=ns.trusted_connection,
            modo_carga=ns.modo_carga,
            generar_historicos=ns.generar_historicos,
        )
