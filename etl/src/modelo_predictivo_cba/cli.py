from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from admin_db_conn.config import ParametrosETL
from admin_db_conn.db import SqlServerDB
from modelo_predictivo_cba.models import ConfiguracionModeloCBA
from modelo_predictivo_cba.service import ServicioModeloCBA


def ejecutar_cli(args: list[str] | None = None) -> int:
    parser = _crear_parser()
    ns = parser.parse_args(args=args)
    parametros = ParametrosETL(
        server=ns.server,
        database=ns.database,
        driver=ns.driver,
        username=ns.username,
        password=ns.password,
        trusted_connection=ns.trusted_connection,
    )
    configuracion = ConfiguracionModeloCBA(
        vista_entrenamiento=ns.vista_entrenamiento,
        vista_prediccion=ns.vista_prediccion,
        ruta_modelo=Path(ns.ruta_modelo),
        ruta_predicciones=Path(ns.ruta_predicciones),
        ruta_validacion=Path(ns.ruta_validacion),
        anio_validacion_preferido=ns.anio_validacion,
        precision_minima_pct=ns.precision_minima,
    )
    servicio = ServicioModeloCBA(
        db=SqlServerDB(parametros),
        configuracion=configuracion,
    )

    if ns.comando == "entrenar":
        resumen = servicio.entrenar()
        print("MODELOS CBA ENTRENADOS")
        print(f"Filas entrenamiento: {resumen.filas_entrenamiento}")
        print(f"Filas validacion: {resumen.filas_validacion}")
        print(f"Tiempo total entrenamiento: {resumen.tiempo_total_entrenamiento_segundos:.4f} s")
        print(f"Precision minima requerida: {resumen.precision_minima_pct:.2f}%")
        _imprimir_metricas(resumen.metricas_algoritmos)
        if resumen.ruta_validacion is not None:
            print(f"CSV validacion: {resumen.ruta_validacion}")
        print("[MODELOS] Archivos generados:")
        for algoritmo, ruta in resumen.rutas_modelos.items():
            print(f"  - {algoritmo}: {ruta}")
        return 0

    if ns.comando == "predecir":
        resultado = servicio.predecir()
        print("PREDICCIONES CBA GENERADAS")
        print(f"Algoritmos utilizados: {', '.join(resultado.algoritmos_utilizados)}")
        print(f"Filas generadas: {resultado.filas_generadas}")
        print(
            "Rango prediccion: "
            f"{resultado.fecha_inicio_prediccion} a {resultado.fecha_fin_prediccion}"
        )
        print(f"Predicciones guardadas en: {resultado.ruta_predicciones}")
        _imprimir_tabla(resultado.ruta_predicciones)
        return 0

    if ns.comando == "comparar-fuente":
        ruta = servicio.comparar_cba_con_fuente_xlsx()
        print("COMPARACION CBA VS XLSX GENERADA")
        print(f"Archivo generado: {ruta}")
        _imprimir_tabla(ruta)
        return 0

    if ns.comando == "validar-vistas":
        resultado = servicio.validar_vistas()
        print("VISTAS CBA VALIDADAS")
        print(f"Vista entrenamiento: {resultado.vista_entrenamiento}")
        print(f"Vista prediccion: {resultado.vista_prediccion}")
        print("Columnas entrenamiento: " + ", ".join(resultado.columnas_entrenamiento))
        print("Columnas prediccion: " + ", ".join(resultado.columnas_prediccion))
        return 0

    if ns.comando == "pipeline":
        print("[PIPELINE] 1/4 Validando vistas del modelo...")
        validacion = servicio.validar_vistas()
        print(f"[PIPELINE] OK entrenamiento: {validacion.vista_entrenamiento}")
        print(f"[PIPELINE] OK prediccion: {validacion.vista_prediccion}")

        print("[PIPELINE] 2/4 Contrastando CBA DW contra los .xlsx oficiales...")
        ruta_comparacion = servicio.comparar_cba_con_fuente_xlsx()
        print(f"[PIPELINE] Comparacion fuente generada en: {ruta_comparacion}")

        print("[PIPELINE] 3/4 Entrenando y validando ambos modelos...")
        entrenamiento = servicio.entrenar()
        print(f"[PIPELINE] Filas entrenamiento: {entrenamiento.filas_entrenamiento}")
        print(f"[PIPELINE] Filas validacion: {entrenamiento.filas_validacion}")
        print(f"[PIPELINE] Tiempo total entrenamiento: {entrenamiento.tiempo_total_entrenamiento_segundos:.4f} s")
        print(f"[PIPELINE] Precision minima requerida: {entrenamiento.precision_minima_pct:.2f}%")
        _imprimir_metricas(entrenamiento.metricas_algoritmos, prefijo="[PIPELINE] ")
        if entrenamiento.ruta_validacion is not None:
            print(f"[PIPELINE] CSV validacion 2025: {entrenamiento.ruta_validacion}")
        print("[PIPELINE] Modelos generados:")
        for algoritmo, ruta in entrenamiento.rutas_modelos.items():
            print(f"  - {algoritmo}: {ruta}")

        print("[PIPELINE] 4/4 Generando pronostico comparado para 2027...")
        prediccion = servicio.predecir(ruta_predicciones=Path(ns.ruta_predicciones))
        print(f"[PIPELINE] Filas generadas: {prediccion.filas_generadas}")
        print(f"[PIPELINE] Algoritmos utilizados: {', '.join(prediccion.algoritmos_utilizados)}")
        print(
            "[PIPELINE] Rango prediccion: "
            f"{prediccion.fecha_inicio_prediccion} a {prediccion.fecha_fin_prediccion}"
        )
        print(f"[PIPELINE] Predicciones guardadas en: {prediccion.ruta_predicciones}")
        print("[PIPELINE] Valores finales de prediccion:")
        _imprimir_tabla(prediccion.ruta_predicciones)
        return 0

    parser.error(f"Comando no soportado: {ns.comando}")
    return 2


def _crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="MODELO_CBA.py",
        description=(
            "Entrena, compara y pronostica el CBA mensual por zona usando las vistas "
            "limpias del DW y los archivos oficiales del INEC."
        ),
    )
    parser.add_argument(
        "comando",
        choices=("entrenar", "predecir", "comparar-fuente", "validar-vistas", "pipeline"),
    )
    parser.add_argument("--server", default=".")
    parser.add_argument("--database", default="DW_Dolar_Canasta")
    parser.add_argument("--driver", default="ODBC Driver 17 for SQL Server")
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument(
        "--trusted-connection",
        dest="trusted_connection",
        action="store_true",
        default=True,
    )
    parser.add_argument(
        "--no-trusted-connection",
        dest="trusted_connection",
        action="store_false",
    )
    parser.add_argument("--vista-entrenamiento", default="dbo.vw_CBA_ModeloSimple_Entrenamiento")
    parser.add_argument("--vista-prediccion", default="dbo.vw_CBA_ModeloSimple_Prediccion")
    parser.add_argument(
        "--ruta-modelo",
        default=str(Path("etl") / "data" / "processed" / "modelo_cba_simple.joblib"),
    )
    parser.add_argument(
        "--ruta-predicciones",
        default=str(Path("etl") / "data" / "processed" / "predicciones_cba_2027.csv"),
    )
    parser.add_argument(
        "--ruta-validacion",
        default=str(Path("etl") / "data" / "processed" / "validacion_cba_2025.csv"),
    )
    parser.add_argument("--anio-validacion", type=int, default=2025)
    parser.add_argument("--precision-minima", type=float, default=85.0)
    return parser


def _imprimir_metricas(metricas: list[dict[str, object]], prefijo: str = "") -> None:
    if not metricas:
        return
    print(f"{prefijo}Metricas por algoritmo:")
    for metrica in metricas:
        print(
            f"{prefijo}  - {metrica['algoritmo']}: "
            f"precision={float(metrica['precision_pct']):.2f}%, "
            f"rango={float(metrica['precision_zona_min_pct']):.2f}% - "
            f"{float(metrica['precision_zona_max_pct']):.2f}%, "
            f"MAE={float(metrica['mae']):.6f}, "
            f"RMSE={float(metrica['rmse']):.6f}, "
            f"R2={float(metrica['r2']):.6f}, "
            f"t_valid={float(metrica.get('tiempo_validacion_segundos', 0.0)):.4f}s, "
            f"t_train={float(metrica.get('tiempo_entrenamiento_segundos', 0.0)):.4f}s"
        )


def _imprimir_tabla(ruta_csv: Path) -> None:
    dataframe = pd.read_csv(ruta_csv, encoding="utf-8-sig")
    columnas = [
        columna
        for columna in dataframe.columns
        if columna in ("FechaMes", "NombreZona", "Zona", "CBA_XLSX", "CBA_DW")
        or columna.startswith("PrediccionCBA_")
    ]
    if not columnas:
        print("No fue posible mostrar el resumen del archivo.")
        return
    vista = dataframe[columnas].copy()
    for columna in vista.columns:
        if columna.startswith("PrediccionCBA_") or columna in ("CBA_XLSX", "CBA_DW"):
            vista[columna] = pd.to_numeric(vista[columna], errors="coerce").round(4)
    print(vista.to_string(index=False))
