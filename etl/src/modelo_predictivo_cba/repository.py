from __future__ import annotations

import warnings

import pandas as pd

from admin_db_conn.db import SqlServerDB
from modelo_predictivo_cba.models import ConfiguracionModeloCBA


class RepositorioModeloCBA:
    def __init__(self, db: SqlServerDB, configuracion: ConfiguracionModeloCBA | None = None) -> None:
        self.db = db
        self.configuracion = configuracion or ConfiguracionModeloCBA()

    def cargar_entrenamiento(self) -> pd.DataFrame:
        self.validar_vista_entrenamiento()
        return self._leer_vista(self.configuracion.vista_entrenamiento)

    def cargar_prediccion(self) -> pd.DataFrame:
        self.validar_vista_prediccion()
        return self._leer_vista(self.configuracion.vista_prediccion)

    def validar_vista_entrenamiento(self) -> list[str]:
        dataframe = self._leer_vista(
            self.configuracion.vista_entrenamiento,
            limite=0,
        )
        self._validar_columnas(
            self.configuracion.vista_entrenamiento,
            dataframe,
            self.configuracion.columnas_requeridas_entrenamiento,
        )
        return list(dataframe.columns)

    def validar_vista_prediccion(self) -> list[str]:
        dataframe = self._leer_vista(
            self.configuracion.vista_prediccion,
            limite=0,
        )
        self._validar_columnas(
            self.configuracion.vista_prediccion,
            dataframe,
            self.configuracion.columnas_requeridas_prediccion,
        )
        return list(dataframe.columns)

    def _leer_vista(self, nombre_vista: str, limite: int | None = None) -> pd.DataFrame:
        consulta = f"SELECT * FROM {nombre_vista}"
        if limite is not None:
            consulta = f"SELECT TOP ({limite}) * FROM {nombre_vista}"
        with self.db.connection() as conn:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="pandas only supports SQLAlchemy connectable",
                    category=UserWarning,
                )
                dataframe = pd.read_sql(consulta, conn)
        if self.configuracion.columna_fecha in dataframe.columns and not dataframe.empty:
            dataframe[self.configuracion.columna_fecha] = pd.to_datetime(
                dataframe[self.configuracion.columna_fecha],
                errors="coerce",
            )
            dataframe = dataframe.sort_values(
                by=[col for col in self.configuracion.columnas_id if col in dataframe.columns]
            ).reset_index(drop=True)
        return dataframe

    @staticmethod
    def _validar_columnas(
        nombre_vista: str,
        dataframe: pd.DataFrame,
        columnas_requeridas: tuple[str, ...],
    ) -> None:
        faltantes = [columna for columna in columnas_requeridas if columna not in dataframe.columns]
        if faltantes:
            raise ValueError(
                f"La vista {nombre_vista} no esta emparejada con el modulo del modelo CBA. "
                f"Faltan columnas: {', '.join(faltantes)}"
            )
