from __future__ import annotations

from pathlib import Path

from etl_clima.models import ConfiguracionExtraccionClima, ZonaClimatica


VARIABLES_NASA = ("T2M_MAX", "T2M_MIN", "PRECTOT", "RH2M", "ALLSKY_SFC_SW_DWN")
ZONAS_BANANO_REFERENCIA = (
    ZonaClimatica(nombre="Matina", latitud=10.00, longitud=-83.35),
    ZonaClimatica(nombre="Siquirres", latitud=10.09, longitud=-83.50),
    ZonaClimatica(nombre="Valle La Estrella", latitud=9.86, longitud=-83.00),
    ZonaClimatica(nombre="Cariari", latitud=10.22, longitud=-83.77),
)


class ExtractorClimaNASA:
    def __init__(
        self,
        ruta_script_referencia: Path | None = None,
        configuracion: ConfiguracionExtraccionClima | None = None,
    ) -> None:
        self.configuracion = configuracion or ConfiguracionExtraccionClima()
        self.ruta_script_referencia = ruta_script_referencia or Path(__file__).with_name("api_nasa.R")

    def obtener_configuracion_peticion(self) -> dict[str, str]:
        return {
            "parameters": ",".join(VARIABLES_NASA),
            "community": "AG",
            "start": self.configuracion.start_year,
            "end": self.configuracion.end_year,
            "format": "JSON",
        }

    def listar_zonas_referencia(self) -> tuple[ZonaClimatica, ...]:
        return ZONAS_BANANO_REFERENCIA

    def cargar_script_referencia(self) -> str:
        return self.ruta_script_referencia.read_text(encoding="utf-8")
