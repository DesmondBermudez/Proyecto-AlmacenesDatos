from __future__ import annotations

from admin_db_conn.db import SqlServerDB
from etl_dolar.models import RegistroTipoCambio


class CargadorDolar:
    def __init__(self, db: SqlServerDB) -> None:
        self.db = db

    def cargar_staging(self, registros: list[RegistroTipoCambio]) -> None:
        with self.db.connection() as conn:
            cursor = conn.cursor()
            for registro in registros:
                cursor.execute(
                    """
                    EXEC dbo.sp_InsertarTipoCambioStaging
                        @Fecha=?,
                        @Compra=?,
                        @Venta=?,
                        @MonedaBaseID=?,
                        @MonedaRefID=?,
                        @FuenteID=?
                    """,
                    (
                        registro.fecha.strftime("%Y-%m-%d"),
                        registro.compra,
                        registro.venta,
                        registro.moneda_base_id,
                        registro.moneda_referencia_id,
                        registro.fuente_id,
                    ),
                )
            conn.commit()
