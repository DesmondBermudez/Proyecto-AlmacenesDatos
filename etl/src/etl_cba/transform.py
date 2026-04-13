from __future__ import annotations

from datetime import datetime

import pandas as pd

from etl_cba.models import FUENTE_INEC, MONTHS_ES_FULL


class TransformadorCBA:
    def transformar_detalle(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        df = dataframe.copy()
        df["Zona"] = df["Zona"].astype(str).str.upper().str.strip()
        df["CategoriaNombre"] = df["CategoriaNombre"].astype(str).str.upper().str.strip()
        df["PeriodoTextoOriginal"] = df["PeriodoTextoOriginal"].astype(str).str.lower().str.strip()
        df["ArchivoOrigen"] = df["ArchivoOrigen"].astype(str).str.strip()
        df["CostoPerCapita"] = pd.to_numeric(df["CostoPerCapita"], errors="coerce")
        df["Fecha"] = df["PeriodoTextoOriginal"].map(self._periodo_a_fecha)
        df["FechaID"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.strftime("%Y%m%d")
        df["FechaID"] = pd.to_numeric(df["FechaID"], errors="coerce").astype("Int64")
        df["FuenteID"] = FUENTE_INEC
        columnas = [
            "Fecha",
            "FechaID",
            "Zona",
            "CategoriaNombre",
            "PeriodoTextoOriginal",
            "CostoPerCapita",
            "ArchivoOrigen",
            "FuenteID",
        ]
        return df[columnas].dropna(
            subset=["Fecha", "FechaID", "Zona", "CategoriaNombre", "CostoPerCapita"]
        )

    def transformar_control(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        df = dataframe.copy()
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.strftime("%Y-%m-%d")
        df["FechaID"] = pd.to_numeric(df["FechaID"], errors="coerce").astype("Int64")
        df["Zona"] = df["Zona"].astype(str).str.upper().str.strip()
        df["CostoPerCapitaControl"] = pd.to_numeric(df["CostoPerCapitaControl"], errors="coerce")
        df["ArchivoOrigenControl"] = df["ArchivoOrigenControl"].astype(str).str.strip()
        columnas = ["Fecha", "FechaID", "Zona", "CostoPerCapitaControl", "ArchivoOrigenControl"]
        return df[columnas].dropna(
            subset=["Fecha", "FechaID", "Zona", "CostoPerCapitaControl"]
        )

    @staticmethod
    def _periodo_a_fecha(periodo: str) -> str | None:
        match = pd.Series([periodo]).str.extract(
            r"^(ene|feb|mar|abr|may|jun|jul|ago|set|oct|nov|dic)-(\d{2})$"
        )
        if match.empty or pd.isna(match.iloc[0, 0]) or pd.isna(match.iloc[0, 1]):
            return None
        mes_token = str(match.iloc[0, 0])
        year_token = int(match.iloc[0, 1])
        month_number = MONTHS_ES_FULL[TransformadorCBA._nombre_mes_completo(mes_token)]
        fecha = datetime(2000 + year_token, month_number, 1)
        return fecha.strftime("%Y-%m-%d")

    @staticmethod
    def _nombre_mes_completo(token: str) -> str:
        equivalencias = {
            "ene": "enero",
            "feb": "febrero",
            "mar": "marzo",
            "abr": "abril",
            "may": "mayo",
            "jun": "junio",
            "jul": "julio",
            "ago": "agosto",
            "set": "setiembre",
            "oct": "octubre",
            "nov": "noviembre",
            "dic": "diciembre",
        }
        return equivalencias[token]
