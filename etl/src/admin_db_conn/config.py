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
    test_full_enabled: bool = False
    test_etl_targets: tuple[str, ...] | None = None
    test_dbconn_enabled: bool = False
    only_test_enabled: bool = False
    modo_carga_indicado: bool = False

    @property
    def es_historico(self) -> bool:
        return self.modo_carga == "historico"

    @property
    def objetivos_prueba_etl(self) -> tuple[str, ...]:
        if self.test_etl_targets is None:
            return ()
        if not self.test_etl_targets or "all" in self.test_etl_targets:
            return ("dolar_canasta", "clima")
        orden = ("dolar_canasta", "clima")
        return tuple(objetivo for objetivo in orden if objetivo in self.test_etl_targets)

    @property
    def debe_ejecutar_pruebas(self) -> bool:
        return self.test_full_enabled or self.test_etl_targets is not None or self.test_dbconn_enabled

    @property
    def debe_ejecutar_pruebas_integrales(self) -> bool:
        return self.test_full_enabled

    @property
    def debe_ejecutar_pruebas_etl(self) -> bool:
        return self.test_full_enabled or self.test_etl_targets is not None

    @property
    def debe_ejecutar_pruebas_dbconn(self) -> bool:
        return self.test_full_enabled or self.test_dbconn_enabled

    @property
    def debe_ejecutar_solo_pruebas(self) -> bool:
        return self.only_test_enabled and self.debe_ejecutar_pruebas

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
