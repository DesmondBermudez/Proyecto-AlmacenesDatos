from __future__ import annotations

import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Generic, TypeVar

import pandas as pd
import requests

from etl_dolar_canasta.models import (
    FUENTE_ARESEP,
    FUENTE_HACIENDA,
    FUENTE_RESPALDO,
    RegistroTipoCambio,
)


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


class ExtractorTipoCambio:
    URL_DIARIA = "https://api.hacienda.go.cr/indicadores/tc/dolar"
    URL_HISTORICA = "https://api.hacienda.go.cr/indicadores/tc/dolar/historico"

    def __init__(self, ruta_respaldo_csv: Path) -> None:
        self.ruta_respaldo_csv = ruta_respaldo_csv

    def obtener_diario(self, guardar_csv: bool = True) -> RegistroTipoCambio:
        resultado = _resolver_con_fallback(
            "tipo de cambio diario",
            api_fetcher=self._obtener_diario_api,
            csv_fetcher=self._obtener_diario_csv,
            simulation_fetcher=self._simular_diario,
            api_source_id=FUENTE_HACIENDA,
        )
        registro = self._clonar_registro(resultado.datos, resultado.fuente_id)
        if guardar_csv:
            self._guardar_registros_csv([registro])
        return registro

    def obtener_historico(self, guardar_csv: bool = True) -> list[RegistroTipoCambio]:
        fecha_fin = datetime.now()
        fecha_actual = datetime(2000, 1, 1)
        registros: list[RegistroTipoCambio] = []
        respaldo = self._leer_respaldo()

        while fecha_actual <= fecha_fin:
            fin_bloque = min(fecha_actual + timedelta(days=30), fecha_fin)
            registros.extend(self._resolver_bloque(fecha_actual, fin_bloque, respaldo))
            fecha_actual = fin_bloque + timedelta(days=1)
        if guardar_csv:
            self._guardar_registros_csv(registros)
        return registros

    def _resolver_bloque(
        self, inicio: datetime, fin: datetime, respaldo: pd.DataFrame
    ) -> list[RegistroTipoCambio]:
        resultado = _resolver_con_fallback(
            f"tipo de cambio historico {inicio:%Y-%m-%d} a {fin:%Y-%m-%d}",
            api_fetcher=lambda: self._obtener_bloque_api(inicio, fin) if inicio.year >= 2015 else [],
            csv_fetcher=lambda: self._obtener_bloque_csv(respaldo, inicio, fin),
            simulation_fetcher=lambda: self._simular_bloque(inicio, fin),
            api_source_id=FUENTE_HACIENDA,
        )
        return [self._clonar_registro(registro, resultado.fuente_id) for registro in resultado.datos]

    def _obtener_diario_api(self) -> RegistroTipoCambio:
        response = requests.get(self.URL_DIARIA, timeout=30)
        response.raise_for_status()
        data = response.json()
        fecha = datetime.fromisoformat(data["venta"]["fecha"].replace("Z", "+00:00")).date()
        return RegistroTipoCambio(
            fecha=fecha,
            compra=float(data["compra"]["valor"]),
            venta=float(data["venta"]["valor"]),
            fuente_id=FUENTE_HACIENDA,
        )

    def _obtener_diario_csv(self) -> RegistroTipoCambio | None:
        respaldo = self._leer_respaldo()
        if respaldo.empty:
            return None
        fila = respaldo.sort_values(by="fecha").iloc[-1]
        return RegistroTipoCambio(
            fecha=fila["fecha"].date(),
            compra=float(fila["compra"]),
            venta=float(fila["venta"]),
            fuente_id=FUENTE_RESPALDO,
        )

    def _simular_diario(self) -> RegistroTipoCambio:
        hoy = datetime.now()
        dif_anios = hoy.year - 2000
        compra = round(308 + (dif_anios * 18) + random.uniform(-0.5, 0.5), 2)
        venta = round(310 + (dif_anios * 18) + random.uniform(-0.5, 0.5), 2)
        return RegistroTipoCambio(
            fecha=hoy.date(),
            compra=compra,
            venta=venta,
            fuente_id=FUENTE_RESPALDO,
        )

    def _obtener_bloque_api(self, inicio: datetime, fin: datetime) -> list[RegistroTipoCambio]:
        response = requests.get(
            self.URL_HISTORICA,
            params={"d": inicio.strftime("%Y-%m-%d"), "h": fin.strftime("%Y-%m-%d")},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        return [
            RegistroTipoCambio(
                fecha=datetime.fromisoformat(item["fecha"].replace("Z", "+00:00")).date(),
                compra=float(item["compra"]),
                venta=float(item["venta"]),
                fuente_id=FUENTE_HACIENDA,
            )
            for item in payload
        ]

    def _leer_respaldo(self) -> pd.DataFrame:
        if not self.ruta_respaldo_csv.exists():
            self._crear_csv_vacio()
            return pd.DataFrame(columns=["fecha", "compra", "venta"])
        df = pd.read_csv(self.ruta_respaldo_csv)
        df["fecha"] = pd.to_datetime(df["fecha"], format="mixed", errors="coerce")
        df = df.dropna(subset=["fecha"])
        df["fecha"] = df["fecha"].dt.normalize()
        return df

    def _crear_csv_vacio(self) -> None:
        self.ruta_respaldo_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["fecha", "compra", "venta"]).to_csv(
            self.ruta_respaldo_csv, index=False, encoding="utf-8-sig"
        )

    def _guardar_registros_csv(self, registros: list[RegistroTipoCambio]) -> None:
        if not registros:
            if not self.ruta_respaldo_csv.exists():
                self._crear_csv_vacio()
            return
        self.ruta_respaldo_csv.parent.mkdir(parents=True, exist_ok=True)
        nuevos = pd.DataFrame(
            [
                {
                    "fecha": registro.fecha.strftime("%Y-%m-%d"),
                    "compra": registro.compra,
                    "venta": registro.venta,
                }
                for registro in registros
            ]
        )
        if self.ruta_respaldo_csv.exists():
            existentes = pd.read_csv(self.ruta_respaldo_csv)
            existentes["fecha"] = pd.to_datetime(
                existentes["fecha"], format="mixed", errors="coerce"
            )
            existentes = existentes.dropna(subset=["fecha"])
            existentes["fecha"] = existentes["fecha"].dt.strftime("%Y-%m-%d")
            combinados = pd.concat([existentes, nuevos], ignore_index=True)
        else:
            combinados = nuevos
        combinados = combinados.drop_duplicates(subset=["fecha"], keep="last")
        combinados = combinados.sort_values(by="fecha")
        combinados.to_csv(self.ruta_respaldo_csv, index=False, encoding="utf-8-sig")

    def _obtener_bloque_csv(
        self, df: pd.DataFrame, inicio: datetime, fin: datetime
    ) -> list[RegistroTipoCambio]:
        if df.empty:
            return []
        filtrado = df[(df["fecha"] >= inicio) & (df["fecha"] <= fin)]
        return [
            RegistroTipoCambio(
                fecha=fila["fecha"].date(),
                compra=float(fila["compra"]),
                venta=float(fila["venta"]),
                fuente_id=FUENTE_RESPALDO,
            )
            for _, fila in filtrado.iterrows()
        ]

    def _simular_bloque(self, inicio: datetime, fin: datetime) -> list[RegistroTipoCambio]:
        bloque: list[RegistroTipoCambio] = []
        cursor = inicio
        while cursor <= fin:
            dif_anios = cursor.year - 2000
            compra = round(308 + (dif_anios * 18) + random.uniform(-0.5, 0.5), 2)
            venta = round(310 + (dif_anios * 18) + random.uniform(-0.5, 0.5), 2)
            bloque.append(
                RegistroTipoCambio(
                    fecha=cursor.date(),
                    compra=compra,
                    venta=venta,
                    fuente_id=FUENTE_RESPALDO,
                )
            )
            cursor += timedelta(days=1)
        return bloque

    def _clonar_registro(self, registro: RegistroTipoCambio, fuente_id: int) -> RegistroTipoCambio:
        return RegistroTipoCambio(
            fecha=registro.fecha,
            compra=registro.compra,
            venta=registro.venta,
            moneda_base_id=registro.moneda_base_id,
            moneda_referencia_id=registro.moneda_referencia_id,
            fuente_id=fuente_id,
        )


class ExtractorCombustible:
    URL = (
        "https://datos.aresep.go.cr/ws.datosabiertos/Services/IE/"
        "TarifaCombustible.svc/ObtenerHistoricoTarifasHidrocarburos"
    )

    def __init__(self, ruta_respaldo_csv: Path) -> None:
        self.ruta_respaldo_csv = ruta_respaldo_csv

    def obtener(self, guardar_csv: bool = True) -> list[dict]:
        resultado = _resolver_con_fallback(
            "historico de combustibles",
            api_fetcher=self._obtener_api,
            csv_fetcher=self._leer_csv,
            simulation_fetcher=self._simular_registros,
            api_source_id=FUENTE_ARESEP,
        )
        registros = self._aplicar_fuente(resultado.datos, resultado.fuente_id)
        if guardar_csv:
            self._guardar_csv(registros)
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
        return df.to_dict(orient="records")

    def _crear_csv_vacio(self) -> None:
        self.ruta_respaldo_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["producto", "precioFinal", "fechaPublicacion"]).to_csv(
            self.ruta_respaldo_csv, index=False, encoding="utf-8-sig"
        )

    def _guardar_csv(self, registros: list[dict]) -> None:
        self.ruta_respaldo_csv.parent.mkdir(parents=True, exist_ok=True)
        if not registros:
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
                for reg in registros
            ]
        )
        if self.ruta_respaldo_csv.exists():
            existentes = pd.read_csv(self.ruta_respaldo_csv)
            combinados = pd.concat([existentes, nuevos], ignore_index=True)
        else:
            combinados = nuevos
        combinados = combinados.drop_duplicates(
            subset=["producto", "precioFinal", "fechaPublicacion"], keep="last"
        )
        combinados.to_csv(self.ruta_respaldo_csv, index=False, encoding="utf-8-sig")

    def _simular_registros(self) -> list[dict]:
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

    def _aplicar_fuente(self, registros: list[dict], fuente_id: int) -> list[dict]:
        return [{**registro, "fuente_id": fuente_id} for registro in registros]


class GeneradorCanasta:
    def __init__(self, ruta_salida: Path) -> None:
        self.ruta_salida = ruta_salida

    def generar(self) -> Path:
        productos = [
            {
                "id": 1,
                "nombre": "Arroz grano entero 80%",
                "categoria": "Cereales",
                "importado": False,
                "unidad": "Kilogramo",
                "precio_base": 820,
            },
            {
                "id": 2,
                "nombre": "Frijoles negros primera calidad",
                "categoria": "Leguminosas",
                "importado": False,
                "unidad": "Gramos",
                "precio_base": 1450,
            },
            {
                "id": 3,
                "nombre": "Leche fluida corta duracion",
                "categoria": "Lacteos",
                "importado": False,
                "unidad": "Mililitros",
                "precio_base": 850,
            },
            {
                "id": 4,
                "nombre": "Tomate",
                "categoria": "Vegetales",
                "importado": False,
                "unidad": "Kilogramo",
                "precio_base": 1500,
            },
            {
                "id": 5,
                "nombre": "Aceite vegetal",
                "categoria": "Grasas",
                "importado": True,
                "unidad": "Mililitros",
                "precio_base": 1450,
            },
        ]
        ubicaciones = [
            {"Provincia": "San Jose", "Canton": "San Jose", "Distrito": "Carmen"},
            {"Provincia": "Alajuela", "Canton": "Alajuela", "Distrito": "Alajuela"},
            {"Provincia": "Cartago", "Canton": "Cartago", "Distrito": "Oriental"},
            {"Provincia": "Heredia", "Canton": "Heredia", "Distrito": "Heredia"},
            {"Provincia": "Limon", "Canton": "Limon", "Distrito": "Limon"},
        ]
        data = []
        fecha_inicio = datetime.now() - timedelta(days=5 * 365)
        for fecha in pd.date_range(start=fecha_inicio, end=datetime.now(), freq="MS"):
            for producto in productos:
                for ubicacion in ubicaciones:
                    variacion = random.uniform(0.95, 1.05)
                    precio = round(producto["precio_base"] * variacion + random.uniform(-10, 10), 2)
                    data.append(
                        {
                            "Fecha": fecha.strftime("%Y-%m-%d"),
                            "ProductoID": producto["id"],
                            "NombreProducto": producto["nombre"],
                            "Categoria": producto["categoria"],
                            "EsImportado": 1 if producto["importado"] else 0,
                            "UnidadMedida": producto["unidad"],
                            "Provincia": ubicacion["Provincia"],
                            "Canton": ubicacion["Canton"],
                            "Distrito": ubicacion["Distrito"],
                            "PrecioColones": precio,
                            "PrecioBaseReferencia": producto["precio_base"],
                            "FactorCanasta": variacion,
                        }
                    )
        self.ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(data).to_csv(self.ruta_salida, index=False, encoding="utf-8-sig")
        return self.ruta_salida
