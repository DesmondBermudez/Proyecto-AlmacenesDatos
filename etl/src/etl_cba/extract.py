from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from etl_cba.models import (
    CONTROL_FILE_PATTERN,
    MONTHS_ES,
    MONTHS_ES_FULL,
    PRODUCT_FILE_PATTERNS,
    ResultadoExtraccionCBA,
    ZONE_LABELS,
)


XML_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
INLINE_TEXT_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"


def normalizar_fecha_inec(valor: object) -> str | None:
    if valor is None:
        return None

    if isinstance(valor, (pd.Timestamp, datetime)):
        return f"{MONTHS_ES[valor.month]}-{str(valor.year)[2:]}"

    if isinstance(valor, (int, float)) and not pd.isna(valor):
        base = datetime(1899, 12, 30)
        dt = base + timedelta(days=float(valor))
        return f"{MONTHS_ES[dt.month]}-{str(dt.year)[2:]}"

    val_str = str(valor).strip().lower()
    if not val_str:
        return None

    if re.fullmatch(r"(ene|feb|mar|abr|may|jun|jul|ago|set|oct|nov|dic)-(\d{2})", val_str):
        return val_str

    if "-" in val_str and len(val_str) >= 8:
        try:
            dt = pd.to_datetime(val_str)
            return f"{MONTHS_ES[dt.month]}-{str(dt.year)[2:]}"
        except Exception:
            pass

    if re.fullmatch(r"\d{5}(?:\.\d+)?", val_str):
        return normalizar_fecha_inec(float(val_str))

    return val_str


class ExtractorCBAOficial:
    def __init__(self, ruta_data_dir: Path) -> None:
        self.ruta_data_dir = ruta_data_dir

    def extraer(self) -> ResultadoExtraccionCBA:
        archivos_detalle = self._resolver_archivos_detalle()
        archivo_control = self._resolver_archivo_control()

        registros_detalle: list[dict] = []
        for archivo in archivos_detalle:
            registros_detalle.extend(self._iter_product_records(archivo))

        if not registros_detalle:
            raise RuntimeError("No se generaron registros de detalle desde los archivos oficiales de CBA.")

        detalle = pd.DataFrame.from_records(registros_detalle)
        detalle = detalle.drop_duplicates().sort_values(["Zona", "CategoriaNombre", "PeriodoTextoOriginal"])

        consolidado = self._leer_consolidado(archivo_control)
        if consolidado.empty:
            raise RuntimeError("No se generaron registros de control desde el consolidado oficial de CBA.")

        consolidado = consolidado.drop_duplicates().sort_values(["Zona", "Fecha"])
        return ResultadoExtraccionCBA(
            detalle=detalle.reset_index(drop=True),
            consolidado=consolidado.reset_index(drop=True),
        )

    def _resolver_archivos_detalle(self) -> list[Path]:
        archivos: list[Path] = []
        for pattern in PRODUCT_FILE_PATTERNS:
            archivos.extend(sorted(self.ruta_data_dir.glob(pattern)))
        if len(archivos) != 3:
            raise FileNotFoundError(
                f"Se esperaban 3 archivos oficiales por zona en {self.ruta_data_dir}, encontrados: {len(archivos)}"
            )
        return archivos

    def _resolver_archivo_control(self) -> Path:
        candidatos = sorted(
            path
            for path in self.ruta_data_dir.glob(CONTROL_FILE_PATTERN)
            if "XMESyProducto" not in path.name
        )
        if not candidatos:
            raise FileNotFoundError(
                f"No se encontró el consolidado mensual oficial en {self.ruta_data_dir}"
            )
        return candidatos[0]

    def _iter_product_records(self, path_xlsx: Path) -> list[dict]:
        rows = self._read_sheet_rows(path_xlsx)

        header_idx = None
        for idx, row in enumerate(rows):
            header_value = str(row.get(1, "") or "").strip().lower()
            if "subgrupo de alimentos" in header_value:
                header_idx = idx
                break

        if header_idx is None:
            raise ValueError(f"No se encontró la fila de encabezados en {path_xlsx.name}")

        zona = "INEC"
        for prefix, label in ZONE_LABELS.items():
            if path_xlsx.name.startswith(prefix):
                zona = label
                break

        period_columns: dict[int, str] = {}
        for col_idx, raw_value in rows[header_idx].items():
            if col_idx < 2:
                continue
            periodo = normalizar_fecha_inec(raw_value)
            if periodo and re.fullmatch(r"(ene|feb|mar|abr|may|jun|jul|ago|set|oct|nov|dic)-\d{2}", periodo):
                period_columns[col_idx] = periodo

        registros: list[dict] = []
        for row in rows[header_idx + 1 :]:
            categoria = str(row.get(1, "") or "").strip()
            if not categoria:
                continue

            for col_idx, periodo in period_columns.items():
                costo = pd.to_numeric(row.get(col_idx), errors="coerce")
                if pd.isna(costo):
                    continue
                registros.append(
                    {
                        "Zona": zona,
                        "CategoriaNombre": categoria,
                        "PeriodoTextoOriginal": periodo,
                        "CostoPerCapita": float(costo),
                        "ArchivoOrigen": path_xlsx.name,
                    }
                )
        return registros

    def _leer_consolidado(self, path_xlsx: Path) -> pd.DataFrame:
        rows = self._read_sheet_rows(path_xlsx)
        registros: list[dict] = []
        zonas_por_columna = {
            3: "Nacional",
            4: "Urbano",
            5: "Rural",
        }

        for row in rows:
            anio_raw = pd.to_numeric(row.get(1), errors="coerce")
            mes = str(row.get(2, "") or "").strip().lower()
            if pd.isna(anio_raw) or mes not in MONTHS_ES_FULL:
                continue

            fecha = datetime(int(anio_raw), MONTHS_ES_FULL[mes], 1)
            for col_idx, zona in zonas_por_columna.items():
                costo = pd.to_numeric(row.get(col_idx), errors="coerce")
                if pd.isna(costo):
                    continue
                registros.append(
                    {
                        "Fecha": fecha.strftime("%Y-%m-%d"),
                        "FechaID": int(fecha.strftime("%Y%m%d")),
                        "Zona": zona,
                        "CostoPerCapitaControl": float(costo),
                        "ArchivoOrigenControl": path_xlsx.name,
                    }
                )
        return pd.DataFrame.from_records(registros)

    def _read_sheet_rows(self, path_xlsx: Path) -> list[dict[int, object]]:
        with ZipFile(path_xlsx) as zip_file:
            shared_strings = self._read_shared_strings(zip_file)
            sheet_root = ET.fromstring(zip_file.read(self._resolve_first_sheet_target(zip_file)))

        rows: list[dict[int, object]] = []
        for row in sheet_root.find("a:sheetData", XML_NS):
            row_data: dict[int, object] = {}
            for cell in row:
                cell_ref = cell.attrib.get("r", "")
                col_idx = self._column_index(cell_ref)
                cell_type = cell.attrib.get("t")
                value_node = cell.find("a:v", XML_NS)
                inline_node = cell.find("a:is", XML_NS)

                value: object = None
                if cell_type == "s" and value_node is not None:
                    value = shared_strings[int(value_node.text)]
                elif cell_type == "inlineStr" and inline_node is not None:
                    value = "".join(node.text or "" for node in inline_node.iter(INLINE_TEXT_NS))
                elif value_node is not None:
                    raw = value_node.text or ""
                    try:
                        value = float(raw)
                    except ValueError:
                        value = raw
                row_data[col_idx] = value
            rows.append(row_data)
        return rows

    @staticmethod
    def _column_index(cell_ref: str) -> int:
        letters = "".join(ch for ch in cell_ref if ch.isalpha())
        index = 0
        for char in letters:
            index = index * 26 + (ord(char.upper()) - ord("A") + 1)
        return index - 1

    @staticmethod
    def _read_shared_strings(zip_file: ZipFile) -> list[str]:
        if "xl/sharedStrings.xml" not in zip_file.namelist():
            return []

        root = ET.fromstring(zip_file.read("xl/sharedStrings.xml"))
        shared_strings: list[str] = []
        for item in root:
            text = "".join(node.text or "" for node in item.iter(INLINE_TEXT_NS))
            shared_strings.append(text)
        return shared_strings

    @staticmethod
    def _resolve_first_sheet_target(zip_file: ZipFile) -> str:
        workbook = ET.fromstring(zip_file.read("xl/workbook.xml"))
        sheets = workbook.find("a:sheets", XML_NS)
        if sheets is None or not list(sheets):
            raise ValueError("El libro de Excel no contiene hojas disponibles.")

        first_sheet = list(sheets)[0]
        relationship_id = first_sheet.attrib[
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        ]
        rels = ET.fromstring(zip_file.read("xl/_rels/workbook.xml.rels"))
        for rel in rels:
            if rel.attrib.get("Id") == relationship_id:
                return f"xl/{rel.attrib['Target']}"
        raise ValueError("No fue posible resolver la hoja principal del archivo Excel.")
