import requests
from datetime import datetime
from src.db import get_connection

URL = "https://api.hacienda.go.cr/indicadores/tc/dolar"

def obtener_tipo_cambio():
    response = requests.get(URL)
    response.raise_for_status()
    return response.json()

def existe_registro(cursor, fecha_id):
    # Corregido: Se pasa como tupla (fecha_id,)
    cursor.execute("SELECT 1 FROM StagingTipoCambio WHERE FechaID = ?", (fecha_id,))
    return cursor.fetchone() is not None

def insertar_staging(data):
    with get_connection() as conn:
        cursor = conn.cursor()

        fecha_str = data['venta']['fecha']
        compra = float(data['compra']['valor'])
        venta = float(data['venta']['valor'])

        try:
            # SINTAXIS RECOMENDADA PARA SQL SERVER / PYODBC
            query = "EXEC sp_InsertarTipoCambioStaging @Fecha=?, @Compra=?, @Venta=?, @MonedaBaseID=?, @MonedaRefID=?, @FuenteID=?"
            params = (fecha_str, compra, venta, 1, 2, 1)
            
            cursor.execute(query, params)
            conn.commit()
            
            print(f"SP ejecutado con éxito para la fecha {fecha_str}")
            
        except Exception as e:
            print(f"Error al ejecutar el SP: {e}")

def run_tipo_cambio():
    try:
        data = obtener_tipo_cambio()
        insertar_staging(data)
    except Exception as e:
        print(f"Error en el proceso: {e}")