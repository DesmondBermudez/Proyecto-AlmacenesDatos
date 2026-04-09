from src.extract.extract_tipo_cambio import run_tipo_cambio
from src.extract.extract_historico import ejecutar_carga_historica
from src.extract.extract_gasolina import cargar_gasolina_a_staging  # Importamos el nuevo módulo
from src.utils.generate_canasta_data import generar_dataset_canasta
from src.load.load_canasta_staging import cargar_canasta_a_staging
from src.load.load_dw import ejecutar_transformacion_dw


def main(cargar_todo=False):
    print("="*50)
    print("🚀 ETL - TIPO DE CAMBIO Y CANASTA BÁSICA")
    print("="*50)

    try:
        if cargar_todo:
            print("\n MODO HISTORICO")
            print("\n1. Poblando históricos...")
            # 1. Cargar Histórico Dólar (5 años)
            ejecutar_carga_historica()
            # 2. Cargar Histórico Gasolina (ARESEP)
            print("\n2. Extrayendo histórico de combustibles desde ARESEP...")
            cargar_gasolina_a_staging()
        else:
            print("\n MODO DIARIO")
            print("\n1. Actualizando datos del día...")
            # 1. Tipo de Cambio (API Hacienda + Fallback CSV)
            run_tipo_cambio()
            print("\n2. Extrayendo histórico de combustibles desde ARESEP...")
            # 2. Gasolina (Dato más reciente de ARESEP)
            cargar_gasolina_a_staging()

        #3
        generar_dataset_canasta()

        #4
        cargar_canasta_a_staging()

        #5
        ejecutar_transformacion_dw()

        print("\n" + "="*50)
        print("PROCESO FINALIZADO EXITOSAMENTE")
        print("="*50)

    except Exception as e:
        print(f"\nERROR CRÍTICO EN EL MAIN: {e}")

if __name__ == "__main__":
    # Cambiar a True para la primera corrida (poblar StagingProducto y Tablas de Hechos)
    # Cambiar a False para la ejecución rutinaria diaria
    INICIO_TOTAL = False 
    
    main(cargar_todo=INICIO_TOTAL)