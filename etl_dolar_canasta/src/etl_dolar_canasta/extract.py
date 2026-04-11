from __future__ import annotations

import random
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from etl_dolar_canasta.models import RegistroTipoCambio


class ExtractorTipoCambio:
    URL_DIARIA = "https://api.hacienda.go.cr/indicadores/tc/dolar"
    URL_HISTORICA = "https://api.hacienda.go.cr/indicadores/tc/dolar/historico"

    def __init__(self, ruta_respaldo_csv: Path) -> None:
        self.ruta_respaldo_csv = ruta_respaldo_csv

    def obtener_diario(self, guardar_csv: bool = True) -> RegistroTipoCambio:
        response = requests.get(self.URL_DIARIA, timeout=30)
        response.raise_for_status()
        data = response.json()
        fecha = datetime.fromisoformat(data["venta"]["fecha"].replace("Z", "+00:00")).date()
        registro = RegistroTipoCambio(
            fecha=fecha,
            compra=float(data["compra"]["valor"]),
            venta=float(data["venta"]["valor"]),
        )
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
            bloque = self._obtener_bloque_api(fecha_actual, fin_bloque) if fecha_actual.year >= 2015 else []
            if not bloque:
                bloque = self._obtener_bloque_csv(respaldo, fecha_actual, fin_bloque)
            if not bloque:
                bloque = self._simular_bloque(fecha_actual, fin_bloque)
            registros.extend(bloque)
            fecha_actual = fin_bloque + timedelta(days=1)
        if guardar_csv:
            self._guardar_registros_csv(registros)
        return registros

    def _obtener_bloque_api(self, inicio: datetime, fin: datetime) -> list[RegistroTipoCambio]:
        try:
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
                )
                for item in payload
            ]
        except Exception:
            return []

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
            bloque.append(RegistroTipoCambio(fecha=cursor.date(), compra=compra, venta=venta))
            cursor += timedelta(days=1)
        return bloque


class ExtractorCombustible:
    URL = (
        "https://datos.aresep.go.cr/ws.datosabiertos/Services/IE/"
        "TarifaCombustible.svc/ObtenerHistoricoTarifasHidrocarburos"
    )

    def __init__(self, ruta_respaldo_csv: Path) -> None:
        self.ruta_respaldo_csv = ruta_respaldo_csv

    def obtener(self, guardar_csv: bool = True) -> list[dict]:
        for _ in range(3):
            try:
                response = requests.get(self.URL, timeout=30)
                response.raise_for_status()
                registros = response.json().get("value", [])
                if guardar_csv:
                    self._guardar_csv(registros)
                return registros
            except Exception:
                time.sleep(3)
        return self._leer_csv()

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


class GeneradorCanasta:
    def __init__(self, ruta_salida: Path) -> None:
        self.ruta_salida = ruta_salida

    def generar(self) -> Path:
        productos = [
            {"id": 1, "nombre": "Arroz grano entero 80%", "categoria": "Cereales", "importado": False, "unidad": "Kilogramo", "precio_base": 820},
            {"id": 2, "nombre": "Frijoles negros primera calidad", "categoria": "Leguminosas", "importado": False, "unidad": "Gramos", "precio_base": 1450},
            {"id": 3, "nombre": "Leche fluida corta duracion", "categoria": "Lacteos", "importado": False, "unidad": "Mililitros", "precio_base": 850},
            {"id": 4, "nombre": "Tomate", "categoria": "Vegetales", "importado": False, "unidad": "Kilogramo", "precio_base": 1500},
            {"id": 5, "nombre": "Aceite vegetal", "categoria": "Grasas", "importado": True, "unidad": "Mililitros", "precio_base": 1450},
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
