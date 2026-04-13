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
        ruta_correlacion=Path(ns.ruta_correlacion),
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
        _imprimir_comparacion_algoritmos(resumen.comparacion_algoritmos)
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
        _imprimir_comparacion_algoritmos(resultado.comparacion_algoritmos)
        _imprimir_metricas(resultado.metricas_algoritmos)
        _imprimir_predicciones_mes_objetivo(resultado.ruta_predicciones)
        return 0

    if ns.comando == "comparar-fuente":
        ruta = servicio.comparar_cba_con_fuente_xlsx()
        print("COMPARACION CBA VS XLSX GENERADA")
        print(f"Archivo generado: {ruta}")
        _imprimir_tabla(ruta)
        return 0

    if ns.comando == "correlacion-exogenas":
        ruta = servicio.generar_matriz_correlacion_exogenas()
        print("MATRIZ DE CORRELACION CBA VS EXOGENAS GENERADA")
        print(f"Archivo generado: {ruta}")
        _imprimir_correlacion_resumen(ruta)
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
        _imprimir_comparacion_algoritmos(entrenamiento.comparacion_algoritmos, prefijo="[PIPELINE] ")
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
        _imprimir_comparacion_algoritmos(prediccion.comparacion_algoritmos, prefijo="[PIPELINE] ")
        print("[PIPELINE] Predicciones del mes equivalente dentro de un ano:")
        _imprimir_predicciones_mes_objetivo(prediccion.ruta_predicciones)
        return 0

    parser.error(f"Comando no soportado: {ns.comando}")
    return 2


def _crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="MODELO_CBA.py",
        description=(
            "Entrena, valida y pronostica la CBA mensual por zona usando el DW.\n"
            "Random Forest se reporta como algoritmo principal y siempre se compara\n"
            "contra regresion lineal sobre el corte historico de validacion."
        ),
        epilog=(
            "Comandos disponibles:\n"
            "  validar-vistas   Verifica que las vistas del DW tengan todas las columnas requeridas.\n"
            "  comparar-fuente  Compara el total oficial de CBA del DW contra los XLSX del INEC.\n"
            "  correlacion-exogenas  Calcula la matriz de correlacion entre CBA y las variables exogenas.\n"
            "  entrenar         Entrena Random Forest y regresion lineal, guarda modelos y CSV de validacion.\n"
            "  predecir         Carga modelos ya entrenados y genera el CSV de los proximos 12 meses.\n"
            "  pipeline         Ejecuta validacion de vistas, comparacion de fuente, entrenamiento y prediccion.\n\n"
            "Archivos generados por defecto:\n"
            "  Modelos: etl/data/processed/modelo_cba_simple_<algoritmo>.joblib\n"
            "  Validacion: etl/data/processed/validacion_cba_2025.csv\n"
            "  Correlacion: etl/data/processed/correlacion_cba_vs_exogenas.csv\n"
            "  Predicciones: etl/data/processed/predicciones_cba_2027.csv\n\n"
            "Ejemplos:\n"
            "  python MODELO_CBA.py validar-vistas --server . --database DW_Dolar_Canasta\n"
            "  python MODELO_CBA.py correlacion-exogenas --ruta-correlacion etl/data/processed/correlacion.csv\n"
            "  python MODELO_CBA.py entrenar --anio-validacion 2025 --precision-minima 85\n"
            "  python MODELO_CBA.py predecir --ruta-predicciones etl/data/processed/predicciones.csv\n"
            "  python MODELO_CBA.py pipeline --server . --database DW_Dolar_Canasta"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "comando",
        choices=("entrenar", "predecir", "comparar-fuente", "correlacion-exogenas", "validar-vistas", "pipeline"),
    )
    parser.add_argument("--server", default=".", help="Servidor o instancia de SQL Server donde vive el DW.")
    parser.add_argument("--database", default="DW_Dolar_Canasta", help="Base de datos del Data Warehouse.")
    parser.add_argument("--driver", default="ODBC Driver 17 for SQL Server", help="Driver ODBC usado para conectarse a SQL Server.")
    parser.add_argument("--username", help="Usuario SQL Server. Si se omite junto con --password, se usa autenticacion integrada.")
    parser.add_argument("--password", help="Contrasena del usuario SQL Server.")
    parser.add_argument(
        "--trusted-connection",
        dest="trusted_connection",
        action="store_true",
        default=True,
        help="Usa autenticacion integrada de Windows. Es el modo predeterminado.",
    )
    parser.add_argument(
        "--no-trusted-connection",
        dest="trusted_connection",
        action="store_false",
        help="Desactiva la autenticacion integrada para usar credenciales SQL.",
    )
    parser.add_argument(
        "--vista-entrenamiento",
        default="dbo.vw_CBA_ModeloSimple_Entrenamiento",
        help="Vista del DW que contiene el dataset historico con target, lags y variables exogenas.",
    )
    parser.add_argument(
        "--vista-prediccion",
        default="dbo.vw_CBA_ModeloSimple_Prediccion",
        help="Vista del DW que contiene las variables futuras para el horizonte de prediccion.",
    )
    parser.add_argument(
        "--ruta-modelo",
        default=str(Path("etl") / "data" / "processed" / "modelo_cba_simple.joblib"),
        help="Ruta base de salida para los modelos. Se guarda un archivo por algoritmo con sufijo _random_forest o _lineal.",
    )
    parser.add_argument(
        "--ruta-predicciones",
        default=str(Path("etl") / "data" / "processed" / "predicciones_cba_2027.csv"),
        help="CSV de salida con 12 meses de prediccion por zona, iniciando el proximo mes.",
    )
    parser.add_argument(
        "--ruta-validacion",
        default=str(Path("etl") / "data" / "processed" / "validacion_cba_2025.csv"),
        help="CSV con el detalle historico del conjunto de validacion y las predicciones de ambos algoritmos.",
    )
    parser.add_argument(
        "--ruta-correlacion",
        default=str(Path("etl") / "data" / "processed" / "correlacion_cba_vs_exogenas.csv"),
        help="CSV de salida para la matriz de correlacion entre CBA y las variables exogenas.",
    )
    parser.add_argument(
        "--anio-validacion",
        type=int,
        default=2025,
        help="Ano usado como conjunto de prueba historico. Si no existe, el servicio usa el tramo temporal mas reciente disponible.",
    )
    parser.add_argument(
        "--precision-minima",
        type=float,
        default=85.0,
        help="Precision porcentual minima exigida al mejor algoritmo durante la validacion historica.",
    )
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
            f"var(pred)={float(metrica['pred_varianza']):.6f}, "
            f"std(pred)={float(metrica['pred_desviacion_std']):.6f}, "
            f"var(error)={float(metrica['error_varianza']):.6f}, "
            f"std(error)={float(metrica['error_desviacion_std']):.6f}, "
            f"t_valid={float(metrica.get('tiempo_validacion_segundos', 0.0)):.4f}s, "
            f"t_train={float(metrica.get('tiempo_entrenamiento_segundos', 0.0)):.4f}s"
        )


def _imprimir_comparacion_algoritmos(
    comparacion: dict[str, object] | None,
    prefijo: str = "",
) -> None:
    if not comparacion:
        return

    precision_rf = comparacion.get("precision_random_forest_pct")
    precision_lineal = comparacion.get("precision_lineal_pct")
    if precision_rf is None or precision_lineal is None:
        print(f"{prefijo}Comparacion RF vs lineal: metricas historicas no disponibles.")
        return

    print(
        f"{prefijo}Comparacion RF vs lineal: "
        f"RF={float(precision_rf):.2f}% | "
        f"Lineal={float(precision_lineal):.2f}% | "
        f"Diferencia={float(comparacion['diferencia_precision_pct']):.2f}% | "
        f"Ganador={comparacion['algoritmo_ganador']}"
    )


def _imprimir_predicciones_mes_objetivo(ruta_csv: Path) -> None:
    dataframe = pd.read_csv(ruta_csv, encoding="utf-8-sig")
    if dataframe.empty or "FechaMes" not in dataframe.columns:
        print("No fue posible mostrar las predicciones del mes objetivo.")
        return

    dataframe["FechaMes"] = pd.to_datetime(dataframe["FechaMes"], errors="coerce")
    fecha_objetivo = dataframe["FechaMes"].max()
    vista = dataframe.loc[dataframe["FechaMes"] == fecha_objetivo].copy()
    columnas = [
        columna
        for columna in ("FechaMes", "NombreZona", "PrediccionCBA_RandomForest", "PrediccionCBA_Lineal")
        if columna in vista.columns
    ]
    vista = vista[columnas]
    for columna in vista.columns:
        if columna.startswith("PrediccionCBA_"):
            vista[columna] = pd.to_numeric(vista[columna], errors="coerce").round(4)
    print(f"Predicciones del mes objetivo ({fecha_objetivo.date()}):")
    print(vista.sort_values(by="NombreZona").to_string(index=False))


def _imprimir_correlacion_resumen(ruta_csv: Path) -> None:
    dataframe = pd.read_csv(ruta_csv, encoding="utf-8-sig")
    if dataframe.empty or "Variable" not in dataframe.columns or "CBA_TotalMensual" not in dataframe.columns:
        print("No fue posible mostrar el resumen de correlacion.")
        return

    vista = dataframe.loc[dataframe["Variable"] != "CBA_TotalMensual", ["Variable", "CBA_TotalMensual"]].copy()
    vista["CBA_TotalMensual"] = pd.to_numeric(vista["CBA_TotalMensual"], errors="coerce").round(4)
    vista = vista.rename(columns={"CBA_TotalMensual": "CorrelacionConCBA"})
    print("Correlacion de cada variable exogena con el CBA:")
    print(
        vista.sort_values(
            by="CorrelacionConCBA",
            key=lambda serie: serie.abs(),
            ascending=False,
        ).to_string(index=False)
    )
