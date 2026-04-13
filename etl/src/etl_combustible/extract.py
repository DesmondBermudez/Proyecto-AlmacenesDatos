from __future__ import annotations

import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Generic, TypeVar

import pandas as pd
import requests

from etl_combustible.combustibles import es_registro_combustible_utilizable
from etl_combustible.models import FUENTE_ARESEP, FUENTE_RESPALDO


T = TypeVar("T")


@dataclass(slots=True)
class ResultadoFuente(Generic[T]):
    datos: T
    fuente_id: int
    origen: str


def _tiene_datos(payload: object) -> bool:
    if payload is None:
        return False
    if isinstance(payload, pd.DataFrame):
        return not payload.empty
    if isinstance(payload, (list, tuple, dict, set, str)):
        return len(payload) > 0
    return True


def _resolver_con_fallback(
    descripcion: str,
    api_fetcher: Callable[[], T | None],
    csv_fetcher: Callable[[], T | None],
    simulation_fetcher: Callable[[], T | None],
    api_source_id: int,
) -> ResultadoFuente[T]:
    errores: list[str] = []
    estrategias = (
        ("api", api_source_id, api_fetcher),
        ("csv", FUENTE_RESPALDO, csv_fetcher),
        ("simulacion", FUENTE_RESPALDO, simulation_fetcher),
    )

    for origen, fuente_id, fetcher in estrategias:
        try:
            payload = fetcher()
        except Exception as exc:
            errores.append(f"{origen}: {exc}")
            continue
        if _tiene_datos(payload):
            return ResultadoFuente(datos=payload, fuente_id=fuente_id, origen=origen)

    detalle = "; ".join(errores) if errores else "sin datos disponibles"
    raise RuntimeError(f"No fue posible obtener {descripcion}. {detalle}")


class ExtractorCombustible:
    URL = (
        "https://datos.aresep.go.cr/ws.datosabiertos/Services/IE/"
        "TarifaCombustible.svc/ObtenerHistoricoTarifasHidrocarburos"
    )

    def __init__(self, ruta_respaldo_csv: Path) -> None:
        self.ruta_respaldo_csv = ruta_respaldo_csv

    def obtener(
        self,
        guardar_csv: bool = True,
        sobrescribir_csv: bool = False,
    ) -> list[dict]:
        resultado = _resolver_con_fallback(
            "historico de combustibles",
            api_fetcher=self._obtener_api,
            csv_fetcher=self._leer_csv,
            simulation_fetcher=self._simular_registros,
            api_source_id=FUENTE_ARESEP,
        )
        registros = self._aplicar_fuente(resultado.datos, resultado.fuente_id)
        if guardar_csv:
            self._guardar_csv(registros, sobrescribir=sobrescribir_csv)
        return registros

    def _obtener_api(self) -> list[dict]:
        ultimo_error: Exception | None = None
        for _ in range(3):
            try:
                response = requests.get(self.URL, timeout=30)
                response.raise_for_status()
                return response.json().get("value", [])
            except Exception as exc:
                ultimo_error = exc
                time.sleep(3)
        if ultimo_error is not None:
            raise ultimo_error
        return []

    def _leer_csv(self) -> list[dict]:
        if not self.ruta_respaldo_csv.exists():
            self._crear_csv_vacio()
            return []
        df = pd.read_csv(self.ruta_respaldo_csv)
        registros = df.to_dict(orient="records")
        return [registro for registro in registros if es_registro_combustible_utilizable(registro)]

    def _crear_csv_vacio(self) -> None:
        self.ruta_respaldo_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["producto", "precioFinal", "fechaPublicacion"]).to_csv(
            self.ruta_respaldo_csv,
            index=False,
            encoding="utf-8-sig",
        )

    def _guardar_csv(self, registros: list[dict], sobrescribir: bool = False) -> None:
        self.ruta_respaldo_csv.parent.mkdir(parents=True, exist_ok=True)
        registros_validos = [
            registro for registro in registros if es_registro_combustible_utilizable(registro)
        ]
        if not registros_validos:
            if not self.ruta_respaldo_csv.exists():
                self._crear_csv_vacio()
            return

        nuevos = pd.DataFrame(
            [
                {
                    "producto": reg.get("producto"),
                    "precioFinal": reg.get("precioFinal"),
                    "fechaPublicacion": reg.get("fechaPublicacion"),
                }
                for reg in registros_validos
            ]
        )
        if self.ruta_respaldo_csv.exists() and not sobrescribir:
            existentes = pd.read_csv(self.ruta_respaldo_csv)
            combinados = pd.concat([existentes, nuevos], ignore_index=True)
        else:
            combinados = nuevos

        combinados = combinados.drop_duplicates(
            subset=["producto", "precioFinal", "fechaPublicacion"],
            keep="last",
        )
        combinados.to_csv(self.ruta_respaldo_csv, index=False, encoding="utf-8-sig")

    @staticmethod
    def _simular_registros() -> list[dict]:
        fecha_publicacion = datetime.now().strftime("%Y-%m-%dT00:00:00")
        return [
            {
                "producto": "Gasolina RON 95",
                "precioFinal": round(785 + random.uniform(-10, 10), 2),
                "fechaPublicacion": fecha_publicacion,
            },
            {
                "producto": "Gasolina RON 91",
                "precioFinal": round(760 + random.uniform(-10, 10), 2),
                "fechaPublicacion": fecha_publicacion,
            },
            {
                "producto": "Diesel",
                "precioFinal": round(690 + random.uniform(-10, 10), 2),
                "fechaPublicacion": fecha_publicacion,
            },
        ]

    @staticmethod
    def _aplicar_fuente(registros: list[dict], fuente_id: int) -> list[dict]:
        return [{**registro, "fuente_id": fuente_id} for registro in registros]
