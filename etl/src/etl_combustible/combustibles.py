from __future__ import annotations

import re
import unicodedata


def normalizar_texto_combustible(valor: object) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""

    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    texto = texto.upper()
    texto = texto.replace("%", " POR CIENTO ")
    texto = texto.replace("PPM", " PPM ")
    texto = texto.replace("-", " ")
    texto = texto.replace("/", " ")
    texto = texto.replace(",", " ")
    texto = texto.replace(".", " ")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def clasificar_producto_combustible(nombre_raw: object) -> dict[str, str] | None:
    texto = normalizar_texto_combustible(nombre_raw)
    if not texto:
        return None

    categoria = "Combustibles"
    unidad = "Litro"

    if "RON 95" in texto or "SUPER" in texto:
        return _producto("Gasolina RON 95", categoria, "Gasolinas", unidad)
    if "RON 91" in texto or "PLUS 91" in texto:
        return _producto("Gasolina RON 91", categoria, "Gasolinas", unidad)
    if "AV GAS" in texto or "AVGAS" in texto:
        return _producto("Av-Gas", categoria, "Gasolinas de aviacion", unidad)
    if "JET" in texto:
        return _producto("Jet Fuel", categoria, "Combustible de aviacion", unidad)
    if "KEROSENO" in texto:
        return _producto("Keroseno", categoria, "Destilados", unidad)
    if "NAFTA" in texto:
        if "PESADA" in texto:
            return _producto("Nafta Pesada", categoria, "Naftas", unidad)
        return _producto("Nafta Liviana", categoria, "Naftas", unidad)
    if "LPG" in texto or "GLP" in texto or "GAS LICUADO DE PETROLEO" in texto:
        if "RICO EN PROPANO" in texto:
            return _producto("GLP Rico en Propano", categoria, "GLP", unidad)
        return _producto("GLP", categoria, "GLP", unidad)
    if "EMULSION ASFALTICA" in texto:
        if "LENTA" in texto or "RL" in texto:
            return _producto("Emulsion Asfaltica Lenta", categoria, "Emulsiones asfalticas", unidad)
        if "RAPIDA" in texto or "RR" in texto:
            return _producto("Emulsion Asfaltica Rapida", categoria, "Emulsiones asfalticas", unidad)
        return _producto("Emulsion Asfaltica", categoria, "Emulsiones asfalticas", unidad)
    if "ASFALTO" in texto:
        if "PG 64 22" in texto:
            return _producto("Asfalto PG-64-22", categoria, "Asfaltos", unidad)
        if "AC 10" in texto:
            return _producto("Asfalto AC-10", categoria, "Asfaltos", unidad)
        if "AC 30" in texto:
            return _producto("Asfalto AC-30", categoria, "Asfaltos", unidad)
        return _producto("Asfalto", categoria, "Asfaltos", unidad)
    if "BUNKER" in texto or "IFO" in texto:
        if "ICE 2" in texto:
            return _producto("Bunker Termico ICE 2", categoria, "Bunker", unidad)
        if "ICE" in texto:
            return _producto("Bunker Termico ICE", categoria, "Bunker", unidad)
        if "BAJO AZUFRE" in texto:
            return _producto("Bunker Bajo Azufre", categoria, "Bunker", unidad)
        if "IFO 180" in texto:
            return _producto("IFO 180", categoria, "Bunker", unidad)
        if "IFO 380" in texto:
            return _producto("IFO 380", categoria, "Bunker", unidad)
        return _producto("Bunker", categoria, "Bunker", unidad)
    if "DIESEL" in texto:
        if "MARINO" in texto:
            return _producto("Diesel Marino", categoria, "Diesel", unidad)
        if "TERMICO" in texto or "GENERACION TERMOELECTRICA" in texto:
            return _producto("Diesel Termico", categoria, "Diesel", unidad)
        if "PESADO" in texto or "GASOLEO" in texto:
            return _producto("Diesel Pesado", categoria, "Diesel", unidad)
        if "PESCADORES" in texto:
            return _producto("Diesel Pescadores", categoria, "Diesel", unidad)
        if "15 PPM" in texto or "15 " in texto:
            return _producto("Diesel 15 ppm", categoria, "Diesel", unidad)
        if "50 PPM" in texto or "50 " in texto:
            return _producto("Diesel 50 ppm", categoria, "Diesel", unidad)
        if "0 05" in texto:
            return _producto("Diesel 0.05% S", categoria, "Diesel", unidad)
        if "0 20" in texto:
            return _producto("Diesel 0.20% S", categoria, "Diesel", unidad)
        if "0 25" in texto:
            return _producto("Diesel 0.25% S", categoria, "Diesel", unidad)
        if "0 35" in texto:
            return _producto("Diesel 0.35% S", categoria, "Diesel", unidad)
        if "0 5" in texto:
            return _producto("Diesel 0.5% S", categoria, "Diesel", unidad)
        return _producto("Diesel", categoria, "Diesel", unidad)

    return _producto(texto.title(), categoria, "Otros hidrocarburos", unidad)


def es_registro_combustible_utilizable(registro: dict) -> bool:
    if clasificar_producto_combustible(registro.get("producto")) is None:
        return False
    if str(registro.get("fechaPublicacion") or "").strip() == "":
        return False
    try:
        return float(registro.get("precioFinal")) > 0
    except (TypeError, ValueError):
        return False


def _producto(nombre: str, categoria: str, subcategoria: str, unidad: str) -> dict[str, str]:
    return {
        "nombre_canonico": nombre,
        "categoria": categoria,
        "subcategoria": subcategoria,
        "unidad_medida": unidad,
    }
