from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable

import pandas as pd

from admin_db_conn.db import SqlServerDB


@dataclass(slots=True)
class PerfilEtapa:
    nombre: str
    filas: int
    columnas_no_nulas: dict[str, int]
    presencia_por_clave: pd.DataFrame


def validar_columnas_obligatorias(
    dataframe: pd.DataFrame,
    columnas: Iterable[str],
    contexto: str,
) -> None:
    columnas_faltantes = [columna for columna in columnas if columna not in dataframe.columns]
    if columnas_faltantes:
        raise ValueError(
            f"{contexto}: faltan columnas obligatorias: {', '.join(columnas_faltantes)}"
        )

    if dataframe.empty:
        raise ValueError(f"{contexto}: no contiene filas para validar.")

    resumen: list[str] = []
    for columna in columnas:
        cantidad_nula = int(dataframe[columna].isna().sum())
        if cantidad_nula > 0:
            resumen.append(f"{columna}={cantidad_nula}")

    if resumen:
        raise ValueError(
            f"{contexto}: se detectaron valores nulos en columnas obligatorias: {', '.join(resumen)}"
        )


class ValidadorTrazabilidad:
    def __init__(
        self,
        dominio: str,
        columnas_clave: Iterable[str],
        columnas_rastreadas: Iterable[str],
    ) -> None:
        self.dominio = dominio
        self.columnas_clave = tuple(columnas_clave)
        self.columnas_rastreadas = tuple(columnas_rastreadas)
        self._perfiles: list[PerfilEtapa] = []

    def registrar_dataframe(self, nombre: str, dataframe: pd.DataFrame) -> PerfilEtapa:
        perfil = self._crear_perfil(nombre, dataframe)
        self._validar_contra_anterior(perfil)
        self._perfiles.append(perfil)
        self._imprimir_resumen(perfil)
        return perfil

    def registrar_csv(self, nombre: str, ruta_csv: Path) -> PerfilEtapa:
        dataframe = pd.read_csv(ruta_csv, encoding="utf-8-sig")
        return self.registrar_dataframe(nombre, dataframe)

    def registrar_sql(
        self,
        nombre: str,
        db: SqlServerDB,
        consulta_sql: str,
        parametros: tuple | None = None,
    ) -> PerfilEtapa:
        with db.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(consulta_sql, parametros or ())
            columnas = [columna[0] for columna in cursor.description]
            filas = cursor.fetchall()
        dataframe = pd.DataFrame.from_records(filas, columns=columnas)
        return self.registrar_dataframe(nombre, dataframe)

    def _crear_perfil(self, nombre: str, dataframe: pd.DataFrame) -> PerfilEtapa:
        columnas_faltantes = [
            columna
            for columna in (*self.columnas_clave, *self.columnas_rastreadas)
            if columna not in dataframe.columns
        ]
        if columnas_faltantes:
            raise ValueError(
                f"{self.dominio}/{nombre}: faltan columnas para trazabilidad: "
                f"{', '.join(columnas_faltantes)}"
            )

        df = dataframe[list((*self.columnas_clave, *self.columnas_rastreadas))].copy()
        for columna in self.columnas_clave:
            df[columna] = df[columna].map(self._normalizar_valor_clave)

        presencia = (
            df.assign(
                **{
                    columna: df[columna].notna()
                    for columna in self.columnas_rastreadas
                }
            )
            .groupby(list(self.columnas_clave), dropna=False, as_index=False)[
                list(self.columnas_rastreadas)
            ]
            .max()
        )

        return PerfilEtapa(
            nombre=nombre,
            filas=int(len(dataframe)),
            columnas_no_nulas={
                columna: int(presencia[columna].astype("boolean").fillna(False).sum())
                for columna in self.columnas_rastreadas
            },
            presencia_por_clave=presencia,
        )

    def _validar_contra_anterior(self, actual: PerfilEtapa) -> None:
        if not self._perfiles:
            return

        anterior = self._perfiles[-1]
        perdidas_resumen: list[str] = []

        for columna in self.columnas_rastreadas:
            anterior_no_nulo = anterior.columnas_no_nulas[columna]
            actual_no_nulo = actual.columnas_no_nulas[columna]
            if actual_no_nulo < anterior_no_nulo:
                perdidas_resumen.append(
                    f"{columna}: {anterior_no_nulo} -> {actual_no_nulo}"
                )

        comparacion = anterior.presencia_por_clave.merge(
            actual.presencia_por_clave,
            on=list(self.columnas_clave),
            how="left",
            suffixes=("_anterior", "_actual"),
        )

        perdidas_por_clave: list[str] = []
        for columna in self.columnas_rastreadas:
            serie_anterior = comparacion[f"{columna}_anterior"].astype("boolean").fillna(False)
            serie_actual = comparacion[f"{columna}_actual"].astype("boolean").fillna(False)
            mascara = (
                serie_anterior
                & ~serie_actual
            )
            if mascara.any():
                ejemplos = comparacion.loc[mascara, list(self.columnas_clave)].head(3)
                claves = ejemplos.to_dict(orient="records")
                perdidas_por_clave.append(f"{columna}: {claves}")

        if perdidas_resumen or perdidas_por_clave:
            detalles = []
            if perdidas_resumen:
                detalles.append("conteos no nulos [" + "; ".join(perdidas_resumen) + "]")
            if perdidas_por_clave:
                detalles.append("claves afectadas [" + "; ".join(perdidas_por_clave) + "]")
            raise RuntimeError(
                f"Trazabilidad rota en {self.dominio}: "
                f"{anterior.nombre} -> {actual.nombre}. {' | '.join(detalles)}"
            )

    def _imprimir_resumen(self, perfil: PerfilEtapa) -> None:
        columnas = ", ".join(
            f"{columna}={cantidad}"
            for columna, cantidad in perfil.columnas_no_nulas.items()
        )
        print(
            f"[TRACE-{self.dominio.upper()}] {perfil.nombre}: "
            f"filas={perfil.filas} | no-nulos -> {columnas}"
        )

    @staticmethod
    def _normalizar_valor_clave(valor: object) -> str:
        if pd.isna(valor):
            return "<NULL>"
        if isinstance(valor, pd.Timestamp):
            return valor.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(valor, datetime):
            return valor.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(valor, date):
            return valor.strftime("%Y-%m-%d")
        if isinstance(valor, Decimal):
            return f"{valor:.6f}"
        if isinstance(valor, bool):
            return str(int(valor))
        if isinstance(valor, int):
            return str(valor)
        if isinstance(valor, float):
            return f"{valor:.6f}"
        return str(valor).strip().upper()


def auditar_tabla_sql_no_nulos(
    db: SqlServerDB,
    tabla: str,
    columnas: Iterable[str],
    where: str | None = None,
) -> dict[str, int]:
    columnas = tuple(columnas)
    if not columnas:
        return {}

    filtro = f" WHERE {where}" if where else ""
    expresiones = ", ".join(
        f"SUM(CASE WHEN [{columna}] IS NULL THEN 1 ELSE 0 END) AS [{columna}]"
        for columna in columnas
    )
    consulta = f"SELECT {expresiones} FROM {tabla}{filtro}"

    with db.connection() as conn:
        cursor = conn.cursor()
        cursor.execute(consulta)
        fila = cursor.fetchone()

    resultado = {
        columna: int(valor or 0)
        for columna, valor in zip(columnas, fila)
    }
    nulos = {columna: cantidad for columna, cantidad in resultado.items() if cantidad > 0}
    if nulos:
        detalle = ", ".join(f"{columna}={cantidad}" for columna, cantidad in nulos.items())
        raise RuntimeError(f"Integridad rota en {tabla}: columnas obligatorias con NULL -> {detalle}")
    print(
        f"[TRACE-SQL] {tabla}: columnas obligatorias sin NULL "
        f"({', '.join(columnas)})"
    )
    return resultado
