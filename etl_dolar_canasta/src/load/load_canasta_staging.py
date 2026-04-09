import pandas as pd
import pyodbc
import os
from src.db import get_connection

def cargar_canasta_a_staging():
    path_csv = "data/raw/historico_canasta_cr.csv"
    
    if not os.path.exists(path_csv):
        print(f"No se encontró el archivo en {path_csv}")
        return

    df = pd.read_csv(path_csv)
    total_registros = len(df)
    print(f"Archivo cargado: {total_registros} registros detectados.")

    with get_connection() as conn:
        cursor = conn.cursor()

        # --- PASO 1: Catálogo de Productos (Carga Única) ---
        # Si quitaste el factor del generador, asegúrate de que estas columnas 
        # existan en el DF o pásalas como constantes 0.0 y 1.0
        columnas_req = ['NombreProducto', 'Categoria', 'UnidadMedida', 'EsImportado']
        productos_unicos = df[columnas_req].drop_duplicates()
        
        print("Sincronizando catálogo de productos...")
        for _, row in productos_unicos.iterrows():
            nombre_norm = str(row['NombreProducto']).upper()
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM StagingProducto WHERE NombreRaw = ? AND FuenteID = 3)
                BEGIN
                    INSERT INTO StagingProducto (NombreRaw, NombreNormalizado, Categoria, UnidadMedida, EsImportado, FuenteID)
                    VALUES (?, ?, ?, ?, ?, 3)
                END
            """, (row['NombreProducto'], row['NombreProducto'], nombre_norm, row['Categoria'], row['UnidadMedida'], row['EsImportado']))
        
        conn.commit()

        # --- PASO 2: Carga de Precios por Lotes (Batching) ---
        print("Limpiando datos previos de la fuente 3...")
        cursor.execute("DELETE FROM StagingHistoricoCanasta WHERE FuenteID = 3")
        conn.commit()

        print("Iniciando carga por lotes para evitar Deadlocks...")
        cursor.fast_executemany = True
        
        # Preparamos los datos
        datos_precios = df[['Fecha', 'NombreProducto', 'Provincia', 'Canton', 'Distrito', 'PrecioColones']].values.tolist()
        datos_precios = [tuple(fila + [3]) for fila in datos_precios]

        # Configuración de lotes (Batch Size)
        batch_size = 10000  # Tamaño recomendado para balancear velocidad y bloqueos
        total_batches = (total_registros // batch_size) + 1

        for i in range(0, total_registros, batch_size):
            lote = datos_precios[i : i + batch_size]
            current_batch = (i // batch_size) + 1
            
            try:
                cursor.executemany("""
                    INSERT INTO StagingHistoricoCanasta (
                        Fecha, NombreProductoRaw, Provincia, Canton, Distrito, PrecioColones, FuenteID
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, lote)
                
                # EL COMMIT POR LOTE ES LA CLAVE: Libera los locks y limpia el log de transacciones
                conn.commit()
                print(f"Lote {current_batch}/{total_batches} procesado ({len(lote)} filas).")
                
            except Exception as e:
                conn.rollback()
                print(f"Error en lote {current_batch}: {e}")
                break

    print(f"Proceso finalizado. Total cargado: {total_registros} registros.")

if __name__ == "__main__":
    cargar_canasta_a_staging()