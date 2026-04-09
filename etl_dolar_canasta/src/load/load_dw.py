from src.db import get_connection
from src.transform.cleaning import limpiar_staging_canasta
import pandas as pd

def ejecutar_transformacion_dw():
    print("⚙️  Iniciando fase de Transformación y Carga al DW...")
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Transformar Fecha (Base de todo el modelo)
            print("  > Procesando StagingFecha -> DimFecha...")
            cursor.execute("EXEC sp_Transform_DimFecha")

            print("  > Procesando DimProducto...")
            cursor.execute("EXEC sp_Transform_DimProducto")

            # PASO 1: Transformación de Dimensiones (SCD)
            print("  > Actualizando DimRegion...")
            cursor.execute("EXEC sp_Transform_DimRegion")
            
            print("  > Actualizando FactTipoCambio...")
            cursor.execute("EXEC [dbo].[sp_Transform_FactTipoCambio]")
            # Aquí podrías llamar a un SP similar para productos
            
            # PASO 2: Carga de la Tabla de Hechos (Fact Table)
            print("  > Poblando FactPreciosCanasta...")
            cursor.execute("EXEC sp_Load_FactPreciosCanasta")
            
            conn.commit()
            print("Data Warehouse actualizado con éxito.")
            
    except Exception as e:
        print(f"Error en la transformación SQL: {e}")
        raise