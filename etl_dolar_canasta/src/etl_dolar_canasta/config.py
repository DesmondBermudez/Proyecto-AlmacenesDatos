from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ParametrosETL:
    server: str = "localhost"
    database: str = "DW_Dolar_Canasta"
    driver: str = "ODBC Driver 17 for SQL Server"
    username: str | None = None
    password: str | None = None
    trusted_connection: bool = True
    modo_carga: str = "direct-insert"
    generar_historicos: bool = True

    @property
    def es_historico(self) -> bool:
        return self.modo_carga == "historico"

    def cadena_conexion(self) -> str:
        partes = [
            f"DRIVER={{{self.driver}}}",
            f"SERVER={self.server}",
            f"DATABASE={self.database}",
            "TrustServerCertificate=yes",
        ]
        if self.username and self.password:
            partes.extend([f"UID={self.username}", f"PWD={self.password}"])
        elif self.trusted_connection:
            partes.append("Trusted_Connection=yes")
        return ";".join(partes)
