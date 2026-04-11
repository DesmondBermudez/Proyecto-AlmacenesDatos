from __future__ import annotations

from pathlib import Path

from etl_dolar_canasta.config import ParametrosETL
from etl_dolar_canasta.db import SqlServerDB
from etl_dolar_canasta.extract import ExtractorCombustible, ExtractorTipoCambio, GeneradorCanasta
from etl_dolar_canasta.load import CargadorDW
from etl_dolar_canasta.transform import TransformadorCanasta, TransformadorCombustible


class ETLDolarCanastaApp:
    def __init__(self, parametros: ParametrosETL, base_dir: Path) -> None:
        self.parametros = parametros
        self.base_dir = base_dir
        self.db = SqlServerDB(parametros)
        self.cargador = CargadorDW(self.db)
        self.extractor_tipo_cambio = ExtractorTipoCambio(
            base_dir / "data" / "raw" / "tipo_cambio_historico.csv"
        )
        self.extractor_combustible = ExtractorCombustible(
            base_dir / "data" / "raw" / "combustible_historico.csv"
        )
        self.generador_canasta = GeneradorCanasta(
            base_dir / "data" / "raw" / "historico_canasta_cr.csv"
        )
        self.transformador_combustible = TransformadorCombustible()
        self.transformador_canasta = TransformadorCanasta()

    def ejecutar(self) -> int:
        print("=" * 50)
        print("ETL - TIPO DE CAMBIO Y CANASTA BASICA")
        print("=" * 50)
        try:
            if self.parametros.es_historico:
                print("Modo historico")
                registros_tc = self.extractor_tipo_cambio.obtener_historico(
                    guardar_csv=self.parametros.generar_historicos
                )
            else:
                print("Modo direct-insert")
                registros_tc = [
                    self.extractor_tipo_cambio.obtener_diario(
                        guardar_csv=self.parametros.generar_historicos
                    )
                ]
            self.cargador.cargar_tipo_cambio(registros_tc)

            registros_combustible = self.extractor_combustible.obtener(
                guardar_csv=self.parametros.generar_historicos
            )
            productos, precios = self.transformador_combustible.transformar(registros_combustible)
            self.cargador.cargar_combustibles(productos, precios)

            ruta_canasta = self.generador_canasta.ruta_salida
            self.generador_canasta.generar()
            df_canasta = self.transformador_canasta.leer_y_transformar(ruta_canasta)
            self.cargador.cargar_canasta(df_canasta)

            self.cargador.asegurar_catalogos_base()
            self.cargador.ejecutar_transformaciones_dw()
            print("Proceso finalizado exitosamente")
            return 0
        except Exception as exc:
            print(f"Error critico en el ETL: {exc}")
            return 1
