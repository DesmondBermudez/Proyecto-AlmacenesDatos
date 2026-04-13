from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd
import requests

from etl_clima.models import ConfiguracionExtraccionClima, ZonaClimatica


COMUNIDAD_NASA = "ag"
VARIABLES_NASA = (
    "T2M_MAX",
    "T2M_MIN",
    "PRECTOT",
    "RH2M",
    "ALLSKY_SFC_SW_DWN",
)
COLUMNAS_CRUDAS_CLIMA = [
    "Zona",
    "Latitud",
    "Longitud",
    "Anio",
    "Mes",
    "Temp_Max",
    "Temp_Min",
    "Precipitacion",
    "Humedad",
    "RadiacionSolar",
]
ZONAS_BANANO_REFERENCIA = (
    ZonaClimatica(nombre="Matina", latitud=10.00, longitud=-83.35),
    ZonaClimatica(nombre="Siquirres", latitud=10.09, longitud=-83.50),
    ZonaClimatica(nombre="Valle La Estrella", latitud=9.86, longitud=-83.00),
    ZonaClimatica(nombre="Cariari", latitud=10.22, longitud=-83.77),
    ZonaClimatica(nombre="La Rita", latitud=10.22, longitud=-83.77),
    ZonaClimatica(nombre="Roxana", latitud=10.25, longitud=-83.72),
    ZonaClimatica(nombre="Guapiles", latitud=10.20, longitud=-83.79),
    ZonaClimatica(nombre="Guacimo", latitud=10.21, longitud=-83.67),
    ZonaClimatica(nombre="Sixaola", latitud=9.50, longitud=-82.85),
    ZonaClimatica(nombre="Talamanca", latitud=9.58, longitud=-82.95),
    ZonaClimatica(nombre="Sarapiqui", latitud=10.40, longitud=-83.80),
    ZonaClimatica(nombre="Barra del Colorado", latitud=10.76, longitud=-83.58),
    ZonaClimatica(nombre="Coto", latitud=8.62, longitud=-82.95),
    ZonaClimatica(nombre="Palmar Sur", latitud=8.96, longitud=-83.48),
    ZonaClimatica(nombre="Rio Claro", latitud=8.71, longitud=-83.06),
    ZonaClimatica(nombre="Golfito", latitud=8.50, longitud=-83.20),
    ZonaClimatica(nombre="Quepos", latitud=9.45, longitud=-84.15),
    ZonaClimatica(nombre="Cahuita", latitud=9.75, longitud=-83.20),
    ZonaClimatica(nombre="Uatsi", latitud=9.65, longitud=-82.95),
    ZonaClimatica(nombre="Turrialba (banano altura)", latitud=9.90, longitud=-83.75),
)


class ExtractorClimaNASA:
    MESES_NASA = {
        "JAN": 1,
        "FEB": 2,
        "MAR": 3,
        "APR": 4,
        "MAY": 5,
        "JUN": 6,
        "JUL": 7,
        "AUG": 8,
        "SEP": 9,
        "OCT": 10,
        "NOV": 11,
        "DEC": 12,
    }

    def __init__(
        self,
        ruta_respaldo_csv: Path | None = None,
        configuracion: ConfiguracionExtraccionClima | None = None,
    ) -> None:
        self.configuracion = configuracion or ConfiguracionExtraccionClima()
        self.configuracion.rango_anios()
        self.ruta_respaldo_csv = ruta_respaldo_csv or (
            Path(__file__).resolve().parents[2] / "data" / "raw" / "clima_historico.csv"
        )

    def obtener_configuracion_peticion(self, community: str = COMUNIDAD_NASA) -> dict[str, str]:
        return {
            "parameters": ",".join(VARIABLES_NASA),
            "community": community,
            "start": self.configuracion.start_year,
            "end": self.configuracion.end_year,
            "format": "CSV",
            "units": "metric",
        }

    def listar_zonas_referencia(self) -> tuple[ZonaClimatica, ...]:
        return ZONAS_BANANO_REFERENCIA

    def obtener(self, guardar_csv: bool = True) -> pd.DataFrame:
        try:
            dataframe_api = self.obtener_desde_api(guardar_csv=False)
        except Exception as exc_api:
            respaldo = self.leer_respaldo_csv()
            if not respaldo.empty:
                return respaldo
            raise RuntimeError(
                "No fue posible obtener datos climaticos desde NASA POWER ni desde el CSV "
                f"de respaldo. Detalle API: {exc_api}"
            ) from exc_api
        dataframe = self._combinar_fuentes(dataframe_api, self.leer_respaldo_csv())
        if dataframe.empty:
            raise RuntimeError("No hay datos climaticos utilizables luego de combinar API y respaldo CSV.")
        if guardar_csv:
            self.guardar_csv(dataframe)
        return dataframe

    def obtener_desde_api(self, guardar_csv: bool = True) -> pd.DataFrame:
        dataframes: list[pd.DataFrame] = []
        errores: list[str] = []

        for zona in self.listar_zonas_referencia():
            try:
                df_zona = self._obtener_zona_api(zona)
            except Exception as exc:
                errores.append(f"{zona.nombre}: {exc}")
                continue
            if not df_zona.empty:
                dataframes.append(df_zona)

        if not dataframes:
            detalle = "; ".join(errores) if errores else "sin datos disponibles"
            raise RuntimeError(f"No fue posible obtener datos climaticos desde NASA POWER. {detalle}")

        dataframe = self._filtrar_registros_utilizables(pd.concat(dataframes, ignore_index=True))
        if dataframe.empty:
            detalle = "; ".join(errores) if errores else "sin datos climaticos completos"
            raise RuntimeError(
                f"No fue posible obtener datos climaticos completos desde NASA POWER. {detalle}"
            )
        if guardar_csv:
            self.guardar_csv(dataframe)
        return dataframe

    def leer_respaldo_csv(self) -> pd.DataFrame:
        if not self.ruta_respaldo_csv.exists():
            self._crear_csv_vacio()
            return self._dataframe_vacio()
        return self._filtrar_registros_utilizables(
            pd.read_csv(self.ruta_respaldo_csv, encoding="utf-8-sig")
        )

    def guardar_csv(self, dataframe: pd.DataFrame) -> Path:
        self.ruta_respaldo_csv.parent.mkdir(parents=True, exist_ok=True)
        self._filtrar_registros_utilizables(dataframe).to_csv(
            self.ruta_respaldo_csv,
            index=False,
            encoding="utf-8-sig",
        )
        return self.ruta_respaldo_csv

    def _crear_csv_vacio(self) -> None:
        self.ruta_respaldo_csv.parent.mkdir(parents=True, exist_ok=True)
        self._dataframe_vacio().to_csv(self.ruta_respaldo_csv, index=False, encoding="utf-8-sig")

    def _dataframe_vacio(self) -> pd.DataFrame:
        return pd.DataFrame(columns=COLUMNAS_CRUDAS_CLIMA)

    def _combinar_fuentes(
        self,
        dataframe_api: pd.DataFrame,
        dataframe_respaldo: pd.DataFrame,
    ) -> pd.DataFrame:
        dataframe_api = self._filtrar_registros_utilizables(dataframe_api)
        dataframe_respaldo = self._filtrar_registros_utilizables(dataframe_respaldo)
        if dataframe_api.empty and dataframe_respaldo.empty:
            return self._dataframe_vacio()

        frames: list[pd.DataFrame] = []
        if not dataframe_respaldo.empty:
            df_respaldo = dataframe_respaldo.copy()
            df_respaldo["_prioridad"] = 0
            frames.append(df_respaldo)
        if not dataframe_api.empty:
            df_api = dataframe_api.copy()
            df_api["_prioridad"] = 1
            frames.append(df_api)

        dataframe = pd.concat(frames, ignore_index=True)
        dataframe = dataframe.sort_values(
            by=["Zona", "Latitud", "Longitud", "Anio", "Mes", "_prioridad"]
        )
        dataframe = dataframe.drop_duplicates(
            subset=["Zona", "Latitud", "Longitud", "Anio", "Mes"],
            keep="last",
        )
        dataframe = dataframe.drop(columns=["_prioridad"])
        return dataframe[COLUMNAS_CRUDAS_CLIMA].reset_index(drop=True)

    def _obtener_zona_api(self, zona: ZonaClimatica) -> pd.DataFrame:
        response = requests.get(
            self.configuracion.base_url,
            params={
                **self.obtener_configuracion_peticion(),
                "longitude": zona.longitud,
                "latitude": zona.latitud,
            },
            headers={"Accept": "text/csv"},
            timeout=60,
        )
        response.raise_for_status()
        dataframe = self._parsear_respuesta_csv(response.text, zona)
        dataframe = self._filtrar_registros_utilizables(dataframe)
        if dataframe.empty:
            raise RuntimeError(f"{zona.nombre}: la API no devolvio filas mensuales utilizables.")
        return dataframe

    def _parsear_respuesta_csv(self, contenido: str, zona: ZonaClimatica) -> pd.DataFrame:
        if not contenido or not contenido.strip():
            return self._dataframe_vacio()

        lineas = [linea.strip() for linea in contenido.replace("\ufeff", "").splitlines()]
        lineas = [linea for linea in lineas if linea]
        if not lineas:
            return self._dataframe_vacio()

        bloque = self._extraer_bloque_tabular_csv(lineas)
        if not bloque:
            raise ValueError("No se encontro el bloque tabular del CSV de NASA POWER.")

        dataframe = pd.read_csv(StringIO("\n".join(bloque)))
        dataframe.columns = [str(columna).strip().upper() for columna in dataframe.columns]
        if "PARAMETER" in dataframe.columns and "YEAR" in dataframe.columns:
            return self._parsear_csv_ancho_por_parametro(dataframe, zona)
        if "YEAR" in dataframe.columns and "MO" in dataframe.columns:
            return self._parsear_csv_largo_por_mes(dataframe, zona)
        raise ValueError(
            "El CSV de NASA POWER no tiene un formato tabular compatible "
            "(esperado: PARAMETER,YEAR,JAN..DEC o YEAR,MO,...)."
        )

    def _parsear_csv_largo_por_mes(self, dataframe: pd.DataFrame, zona: ZonaClimatica) -> pd.DataFrame:
        registros: list[dict[str, object]] = []
        for _, fila in dataframe.iterrows():
            anio = self._normalizar_entero(fila.get("YEAR"))
            mes = self._normalizar_entero(fila.get("MO"))
            if anio is None or mes is None or mes < 1 or mes > 12:
                continue
            registros.append(
                {
                    "Zona": zona.nombre,
                    "Latitud": zona.latitud,
                    "Longitud": zona.longitud,
                    "Anio": anio,
                    "Mes": mes,
                    "Temp_Max": self._normalizar_valor(fila.get("T2M_MAX")),
                    "Temp_Min": self._normalizar_valor(fila.get("T2M_MIN")),
                    "Precipitacion": self._resolver_precipitacion(fila),
                    "Humedad": self._normalizar_valor(fila.get("RH2M")),
                    "RadiacionSolar": self._normalizar_valor(fila.get("ALLSKY_SFC_SW_DWN")),
                }
            )
        return self._materializar_registros(registros)

    def _parsear_csv_ancho_por_parametro(
        self,
        dataframe: pd.DataFrame,
        zona: ZonaClimatica,
    ) -> pd.DataFrame:
        pivot: dict[int, dict[str, object]] = {}

        for _, fila in dataframe.iterrows():
            parametro = str(fila.get("PARAMETER", "")).strip().upper()
            anio = self._normalizar_entero(fila.get("YEAR"))
            if not parametro or anio is None:
                continue
            for nombre_mes, mes in self.MESES_NASA.items():
                clave = (anio, mes)
                bucket = pivot.setdefault(
                    clave,
                    {
                        "Zona": zona.nombre,
                        "Latitud": zona.latitud,
                        "Longitud": zona.longitud,
                        "Anio": anio,
                        "Mes": mes,
                        "Temp_Max": None,
                        "Temp_Min": None,
                        "Precipitacion": None,
                        "Humedad": None,
                        "RadiacionSolar": None,
                    },
                )
                valor = self._normalizar_valor(fila.get(nombre_mes))
                if parametro == "T2M_MAX":
                    bucket["Temp_Max"] = valor
                elif parametro == "T2M_MIN":
                    bucket["Temp_Min"] = valor
                elif parametro in ("PRECTOT", "PRECTOTCORR"):
                    if bucket["Precipitacion"] is None and valor is not None:
                        bucket["Precipitacion"] = valor
                elif parametro == "RH2M":
                    bucket["Humedad"] = valor
                elif parametro == "ALLSKY_SFC_SW_DWN":
                    bucket["RadiacionSolar"] = valor

        return self._materializar_registros(list(pivot.values()))

    def _materializar_registros(self, registros: list[dict[str, object]]) -> pd.DataFrame:
        if not registros:
            return self._dataframe_vacio()
        return self._filtrar_registros_utilizables(
            pd.DataFrame(registros, columns=COLUMNAS_CRUDAS_CLIMA)
        )

    def _extraer_bloque_tabular_csv(self, lineas: list[str]) -> list[str]:
        inicio = None
        for indice, linea in enumerate(lineas):
            if linea.upper() == "-END HEADER-":
                continue
            columnas = [col.strip().upper() for col in linea.split(",")]
            if ("YEAR" in columnas and "MO" in columnas) or (
                "PARAMETER" in columnas and "YEAR" in columnas
            ):
                inicio = indice
                break
        if inicio is None:
            return []

        bloque: list[str] = []
        for linea in lineas[inicio:]:
            if linea.startswith("-END"):
                break
            bloque.append(linea)
        return bloque

    def _resolver_precipitacion(self, fila: pd.Series) -> float | None:
        for variable in ("PRECTOT", "PRECTOTCORR"):
            valor = self._normalizar_valor(fila.get(variable))
            if valor is not None:
                return valor
        return None

    def _normalizar_entero(self, valor: object) -> int | None:
        numero = self._normalizar_valor(valor)
        if numero is None:
            return None
        return int(numero)

    def _normalizar_valor(self, valor: object) -> float | None:
        if valor in (None, ""):
            return None
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            return None
        if numero <= -900:
            return None
        return numero

    def _filtrar_registros_utilizables(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        if dataframe.empty:
            return self._dataframe_vacio()

        df = dataframe.copy()
        columnas_numericas = [
            "Latitud",
            "Longitud",
            "Anio",
            "Mes",
            "Temp_Max",
            "Temp_Min",
            "Precipitacion",
            "Humedad",
            "RadiacionSolar",
        ]
        for columna in columnas_numericas:
            if columna in df.columns:
                df[columna] = pd.to_numeric(df[columna], errors="coerce")
        if "Zona" in df.columns:
            df["Zona"] = df["Zona"].astype(str).str.upper().str.strip()
        df = df.dropna(
            subset=[
                "Zona",
                "Latitud",
                "Longitud",
                "Anio",
                "Mes",
                "Temp_Max",
                "Temp_Min",
                "Precipitacion",
                "Humedad",
                "RadiacionSolar",
            ]
        )
        df["Anio"] = df["Anio"].astype(int)
        df["Mes"] = df["Mes"].astype(int)
        return df[COLUMNAS_CRUDAS_CLIMA].reset_index(drop=True)
