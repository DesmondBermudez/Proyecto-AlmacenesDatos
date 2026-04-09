import pandas as pd

def transformar_datos_canasta(df):
    """
    Limpia los datos de Staging antes de procesar las dimensiones en SQL.
    """
    # 1. Normalización de Texto (Crucial para JOINs en SQL)
    columnas_texto = ['Provincia', 'Canton', 'Distrito', 'NombreProductoRaw']
    for col in columnas_texto:
        if col in df.columns:
            # Quitamos espacios, tildes (opcional) y pasamos a MAYÚSCULAS
            df[col] = df[col].astype(str).str.upper().str.strip()
    
    # 2. Validación de Precios
    # Convertimos a numérico y eliminamos lo que no sea un número válido
    df['PrecioColones'] = pd.to_numeric(df['PrecioColones'], errors='coerce')
    df = df.dropna(subset=['PrecioColones'])
    
    # 3. Formato de Fecha
    df['Fecha'] = pd.to_datetime(df['Fecha']).dt.strftime('%Y-%m-%d')
    
    return df