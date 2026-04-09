import requests
import time
from src.db import get_connection

URL_ARESEP = "https://datos.aresep.go.cr/ws.datosabiertos/Services/IE/TarifaCombustible.svc/ObtenerHistoricoTarifasHidrocarburos"

def extraer_datos_aresep():
    for i in range(3):
        try:
            print(f"Conectando a ARESEP (Intento {i+1})...")
            response = requests.get(URL_ARESEP, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get('value', [])
        except Exception as e:
            print(f"Error de conexión: {e}")
            time.sleep(3)
    return []

def cargar_gasolina_a_staging():
    registros = extraer_datos_aresep()
    if not registros:
        return

    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Limpiamos el staging de productos de esta fuente
        cursor.execute("DELETE FROM StagingProducto WHERE FuenteID = 3")

        print(f"Procesando y filtrando registros de ARESEP...")
        
        productos_vistos = set()
        conteo_precios = 0

        for reg in registros:
            nombre_raw = reg.get('producto', '')
            if not nombre_raw:
                continue
                
            nombre_raw_strip = nombre_raw.strip()
            nombre_upper = nombre_raw_strip.upper()
            
            nombre_normalizado = None

            # --- LÓGICA DE FILTRADO DINÁMICO ---
            if "RON 95" in nombre_upper:
                nombre_normalizado = "Gasolina RON 95"
            elif "RON 91" in nombre_upper:
                nombre_normalizado = "Gasolina RON 91"
            elif "DIÉSEL" in nombre_upper or "DIESEL" in nombre_upper:
                # Esto captura "Diésel", "Diésel 50 ppm", "Diésel automotriz", etc.
                nombre_normalizado = "Diésel"

            # Si el producto no es uno de los 3 que buscamos, saltamos
            if not nombre_normalizado:
                continue

            precio = reg.get('precioFinal')
            fecha = reg.get('fechaPublicacion')

            # 1. Insertar en StagingProducto
            if nombre_raw_strip not in productos_vistos:
                cursor.execute("""
                    INSERT INTO StagingProducto (
                        NombreRaw, NombreNormalizado, Categoria, 
                        SubCategoria, UnidadMedida, FuenteID
                    ) 
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (nombre_raw_strip, nombre_normalizado, 'Combustibles', 'Hidrocarburos', 'Litro', 2))
                productos_vistos.add(nombre_raw_strip)

            # 2. Cargar en StagingPrecioGasolina
            if precio is not None:
                cursor.execute("""
                    INSERT INTO StagingPrecioGasolina (FechaRaw, NombreProductoRaw, Precio, FuenteID)
                    VALUES (?, ?, ?, 3)
                """, (fecha, nombre_raw_strip, precio))
                conteo_precios += 1

        conn.commit()
        print(f"Extracción finalizada con filtros.")
        print(f"Registros de precios cargados: {conteo_precios}")

if __name__ == "__main__":
    cargar_gasolina_a_staging()