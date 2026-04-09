import pandas as pd

def limpiar_staging_canasta(df):
    """Estandariza los datos antes de que SQL intente hacer JOINs."""
    # Normalizar geografía y productos
    cols_to_fix = ['Provincia', 'Canton', 'Distrito', 'NombreProductoRaw']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = df[col].astype(str).str.upper().str.strip()
    
    # Asegurar que el precio sea válido
    df['PrecioColones'] = pd.to_numeric(df['PrecioColones'], errors='coerce')
    return df.dropna(subset=['PrecioColones'])