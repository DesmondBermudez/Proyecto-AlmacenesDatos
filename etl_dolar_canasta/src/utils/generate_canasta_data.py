import pandas as pd
import numpy as np
import random
import os
from datetime import datetime, timedelta

def generar_dataset_canasta():
    # 1. Definición de Productos Reales de la CBA Costa Rica (Estructura de Diccionario)

    # El 'precio_base' es una referencia histórica (₡)
    # El 'factor' representa el consumo mensual promedio por persona
    # 1. Definición de los 52 Productos Reales de la CBA Costa Rica (Sin Factor)
    productos_base = [
        # --- CEREALES ---
        {"id": 1, "nombre": "Arroz grano entero 80%", "categoria": "Cereales", "importado": False, "unidad": "Kilogramo", "precio_base": 820},
        {"id": 2, "nombre": "Arroz grano entero 95%", "categoria": "Cereales", "importado": False, "unidad": "Kilogramo", "precio_base": 950},
        {"id": 3, "nombre": "Pan blanco tipo bolillo/baguette", "categoria": "Cereales", "importado": False, "unidad": "Unidades", "precio_base": 150},
        {"id": 4, "nombre": "Pan cuadrado", "categoria": "Cereales", "importado": False, "unidad": "Gramos", "precio_base": 1450},
        {"id": 5, "nombre": "Galletas dulces", "categoria": "Cereales", "importado": False, "unidad": "Gramos", "precio_base": 450},
        {"id": 6, "nombre": "Galletas saladas (Soda)", "categoria": "Cereales", "importado": False, "unidad": "Gramos", "precio_base": 600},
        {"id": 7, "nombre": "Tortilla de maíz (paquete)", "categoria": "Cereales", "importado": False, "unidad": "Unidades", "precio_base": 550},
        {"id": 8, "nombre": "Pastas alimenticias (Espagueti)", "categoria": "Cereales", "importado": True, "unidad": "Gramos", "precio_base": 650},
        {"id": 9, "nombre": "Avena en hojuelas", "categoria": "Cereales", "importado": True, "unidad": "Gramos", "precio_base": 900},

        # --- CARNES Y PROTEÍNAS ---
        {"id": 10, "nombre": "Bistec de res (Posta Cuarta)", "categoria": "Proteínas", "importado": False, "unidad": "Kilogramo", "precio_base": 5800},
        {"id": 11, "nombre": "Carne molida de res (de primera)", "categoria": "Proteínas", "importado": False, "unidad": "Kilogramo", "precio_base": 4500},
        {"id": 12, "nombre": "Chuleta de cerdo", "categoria": "Proteínas", "importado": False, "unidad": "Kilogramo", "precio_base": 3900},
        {"id": 13, "nombre": "Pollo entero sin menudos", "categoria": "Proteínas", "importado": False, "unidad": "Kilogramo", "precio_base": 2400},
        {"id": 14, "nombre": "Muslo de pollo", "categoria": "Proteínas", "importado": False, "unidad": "Kilogramo", "precio_base": 2100},
        {"id": 15, "nombre": "Atún en aceite (lata)", "categoria": "Proteínas", "importado": True, "unidad": "Gramos", "precio_base": 1100},
        {"id": 16, "nombre": "Huevos de gallina", "categoria": "Proteínas", "importado": False, "unidad": "Kilogramo", "precio_base": 2100},
        {"id": 17, "nombre": "Pescado (Filete de bolado/pargo)", "categoria": "Proteínas", "importado": False, "unidad": "Kilogramo", "precio_base": 6500},
        {"id": 18, "nombre": "Salchichón", "categoria": "Proteínas", "importado": False, "unidad": "Kilogramo", "precio_base": 3200},

        # --- LÁCTEOS ---
        {"id": 19, "nombre": "Leche fluida corta duración", "categoria": "Lácteos", "importado": False, "unidad": "Mililitros", "precio_base": 850},
        {"id": 20, "nombre": "Leche en polvo entera", "categoria": "Lácteos", "importado": False, "unidad": "Gramos", "precio_base": 2800},
        {"id": 21, "nombre": "Queso tierno (blanco)", "categoria": "Lácteos", "importado": False, "unidad": "Kilogramo", "precio_base": 4200},
        {"id": 22, "nombre": "Natilla", "categoria": "Lácteos", "importado": False, "unidad": "Gramos", "precio_base": 950},

        # --- LEGUMINOSAS ---
        {"id": 23, "nombre": "Frijoles negros primera calidad", "categoria": "Leguminosas", "importado": False, "unidad": "Gramos", "precio_base": 1450},
        {"id": 24, "nombre": "Frijoles rojos primera calidad", "categoria": "Leguminosas", "importado": False, "unidad": "Gramos", "precio_base": 1600},

        # --- VEGETALES Y VERDURAS ---
        {"id": 25, "nombre": "Papa blanca", "categoria": "Vegetales", "importado": False, "unidad": "Kilogramo", "precio_base": 1100},
        {"id": 26, "nombre": "Cebolla blanca/morada", "categoria": "Vegetales", "importado": False, "unidad": "Kilogramo", "precio_base": 1300},
        {"id": 27, "nombre": "Tomate", "categoria": "Vegetales", "importado": False, "unidad": "Kilogramo", "precio_base": 1500},
        {"id": 28, "nombre": "Zanahoria", "categoria": "Vegetales", "importado": False, "unidad": "Kilogramo", "precio_base": 650},
        {"id": 29, "nombre": "Chayote", "categoria": "Vegetales", "importado": False, "unidad": "Unidades", "precio_base": 450},
        {"id": 30, "nombre": "Repollo blanco", "categoria": "Vegetales", "importado": False, "unidad": "Kilogramo", "precio_base": 900},
        {"id": 31, "nombre": "Culantro", "categoria": "Vegetales", "importado": False, "unidad": "Rollos", "precio_base": 350},
        {"id": 32, "nombre": "Yuca", "categoria": "Vegetales", "importado": False, "unidad": "Kilogramo", "precio_base": 850},

        # --- FRUTAS ---
        {"id": 33, "nombre": "Banano maduro", "categoria": "Frutas", "importado": False, "unidad": "Unidades", "precio_base": 60},
        {"id": 34, "nombre": "Plátano maduro/verde", "categoria": "Frutas", "importado": False, "unidad": "Unidades", "precio_base": 250},
        {"id": 35, "nombre": "Naranja (jugo)", "categoria": "Frutas", "importado": False, "unidad": "Unidades", "precio_base": 120},
        {"id": 36, "nombre": "Papaya", "categoria": "Frutas", "importado": False, "unidad": "Kilogramo", "precio_base": 900},
        {"id": 37, "nombre": "Sandía", "categoria": "Frutas", "importado": False, "unidad": "Kilogramo", "precio_base": 750},
        {"id": 38, "nombre": "Limón mesino/ácido", "categoria": "Frutas", "importado": False, "unidad": "Unidades", "precio_base": 150},

        # --- GRASAS Y ACEITES ---
        {"id": 39, "nombre": "Aceite vegetal", "categoria": "Grasas", "importado": True, "unidad": "Mililitros", "precio_base": 1450},
        {"id": 40, "nombre": "Margarina", "categoria": "Grasas", "importado": False, "unidad": "Gramos", "precio_base": 650},
        {"id": 41, "nombre": "Manteca de cerdo/vegetal", "categoria": "Grasas", "importado": False, "unidad": "Gramos", "precio_base": 900},

        # --- ABARROTES Y AZÚCARES ---
        {"id": 42, "nombre": "Azúcar blanca", "categoria": "Abarrotes", "importado": False, "unidad": "Kilogramo", "precio_base": 780},
        {"id": 43, "nombre": "Sal regular", "categoria": "Abarrotes", "importado": False, "unidad": "Gramos", "precio_base": 450},
        {"id": 44, "nombre": "Café molido puro", "categoria": "Bebidas", "importado": False, "unidad": "Gramos", "precio_base": 3200},
        {"id": 45, "nombre": "Salsa de tomate", "categoria": "Abarrotes", "importado": False, "unidad": "Gramos", "precio_base": 850},
        {"id": 46, "nombre": "Mayonesa", "categoria": "Abarrotes", "importado": True, "unidad": "Gramos", "precio_base": 1200},
        {"id": 47, "nombre": "Condimentos/Consomé", "categoria": "Abarrotes", "importado": False, "unidad": "Gramos", "precio_base": 250},
        {"id": 48, "nombre": "Bebida en polvo (sirope/refresco)", "categoria": "Bebidas", "importado": False, "unidad": "Gramos", "precio_base": 400},

        # --- OTROS ---
        {"id": 49, "nombre": "Harina de maíz", "categoria": "Harinas", "importado": False, "unidad": "Kilogramo", "precio_base": 1100},
        {"id": 50, "nombre": "Harina de trigo", "categoria": "Harinas", "importado": True, "unidad": "Kilogramo", "precio_base": 1250},
        {"id": 51, "nombre": "Agua embotellada", "categoria": "Bebidas", "importado": False, "unidad": "Mililitros", "precio_base": 600},
        {"id": 52, "nombre": "Alimento para bebé (colado)", "categoria": "Abarrotes", "importado": False, "unidad": "Gramos", "precio_base": 750}
    ]

    # MAPEADOR DE FACTORES (Consumo mensual promedio en CR)
    # Esto simula cuánto de cada categoría consume un hogar
    dict_factores = {
        "Cereales": 4.5,
        "Grasas": 1.2,
        "Proteínas": 2.8,
        "Leguminosas": 1.5,
        "Lácteos": 6.0,
        "Abarrotes": 0.8,
        "Bebidas": 2.0,
        "Harinas": 1.5,
        "Embutidos": 1.0
    }

    # 2. Ubicaciones
    ubicaciones = [
        # --- SAN JOSÉ ---
        {"Provincia": "San José", "Canton": "San José", "Distrito": "Carmen"},
        {"Provincia": "San José", "Canton": "San José", "Distrito": "Merced"},
        {"Provincia": "San José", "Canton": "Escazú", "Distrito": "Escazú Centro"},
        {"Provincia": "San José", "Canton": "Desamparados", "Distrito": "Desamparados"},
        {"Provincia": "San José", "Canton": "Pérez Zeledón", "Distrito": "San Isidro de El General"},
        {"Provincia": "San José", "Canton": "Goicoechea", "Distrito": "Guadalupe"},
        {"Provincia": "San José", "Canton": "Santa Ana", "Distrito": "Santa Ana"},
        {"Provincia": "San José", "Canton": "Curridabat", "Distrito": "Curridabat"},
        {"Provincia": "San José", "Canton": "Puriscal", "Distrito": "Santiago"},

        # --- ALAJUELA ---
        {"Provincia": "Alajuela", "Canton": "Alajuela", "Distrito": "Alajuela"},
        {"Provincia": "Alajuela", "Canton": "Alajuela", "Distrito": "San José"},
        {"Provincia": "Alajuela", "Canton": "San Carlos", "Distrito": "Quesada"},
        {"Provincia": "Alajuela", "Canton": "San Carlos", "Distrito": "La Fortuna"},
        {"Provincia": "Alajuela", "Canton": "Grecia", "Distrito": "Grecia"},
        {"Provincia": "Alajuela", "Canton": "Sarchí", "Distrito": "Sarchí Norte"},
        {"Provincia": "Alajuela", "Canton": "Upala", "Distrito": "Upala"},
        {"Provincia": "Alajuela", "Canton": "Palmares", "Distrito": "Palmares"},

        # --- CARTAGO ---
        {"Provincia": "Cartago", "Canton": "Cartago", "Distrito": "Oriental"},
        {"Provincia": "Cartago", "Canton": "Cartago", "Distrito": "Occidental"},
        {"Provincia": "Cartago", "Canton": "La Unión", "Distrito": "Tres Ríos"},
        {"Provincia": "Cartago", "Canton": "Paraíso", "Distrito": "Paraíso"},
        {"Provincia": "Cartago", "Canton": "Turrialba", "Distrito": "Turrialba"},
        {"Provincia": "Cartago", "Canton": "Oreamuno", "Distrito": "San Rafael"},
        {"Provincia": "Cartago", "Canton": "El Guarco", "Distrito": "Tejar"},

        # --- HEREDIA ---
        {"Provincia": "Heredia", "Canton": "Heredia", "Distrito": "Heredia"},
        {"Provincia": "Heredia", "Canton": "Heredia", "Distrito": "San Francisco"},
        {"Provincia": "Heredia", "Canton": "Barva", "Distrito": "Barva"},
        {"Provincia": "Heredia", "Canton": "Sarapiquí", "Distrito": "Puerto Viejo"},
        {"Provincia": "Heredia", "Canton": "Santo Domingo", "Distrito": "Santo Domingo"},
        {"Provincia": "Heredia", "Canton": "San Rafael", "Distrito": "San Rafael"},
        {"Provincia": "Heredia", "Canton": "Belén", "Distrito": "San Antonio"},

        # --- GUANACASTE ---
        {"Provincia": "Guanacaste", "Canton": "Liberia", "Distrito": "Liberia"},
        {"Provincia": "Guanacaste", "Canton": "Nicoya", "Distrito": "Nicoya"},
        {"Provincia": "Guanacaste", "Canton": "Santa Cruz", "Distrito": "Santa Cruz"},
        {"Provincia": "Guanacaste", "Canton": "Bagaces", "Distrito": "Bagaces"},
        {"Provincia": "Guanacaste", "Canton": "Cañas", "Distrito": "Cañas"},
        {"Provincia": "Guanacaste", "Canton": "Tilarán", "Distrito": "Tilarán"},
        {"Provincia": "Guanacaste", "Canton": "La Cruz", "Distrito": "La Cruz"},

        # --- PUNTARENAS ---
        {"Provincia": "Puntarenas", "Canton": "Puntarenas", "Distrito": "Puntarenas"},
        {"Provincia": "Puntarenas", "Canton": "Puntarenas", "Distrito": "El Roble"},
        {"Provincia": "Puntarenas", "Canton": "Esparza", "Distrito": "Espíritu Santo"},
        {"Provincia": "Puntarenas", "Canton": "Quepos", "Distrito": "Quepos"},
        {"Provincia": "Puntarenas", "Canton": "Golfito", "Distrito": "Golfito"},
        {"Provincia": "Puntarenas", "Canton": "Osa", "Distrito": "Ciudad Cortés"},
        {"Provincia": "Puntarenas", "Canton": "Garabito", "Distrito": "Jacó"},
        {"Provincia": "Puntarenas", "Canton": "Corredores", "Distrito": "Paso Canoas"},

        # --- LIMÓN ---
        {"Provincia": "Limón", "Canton": "Limón", "Distrito": "Limón"},
        {"Provincia": "Limón", "Canton": "Pococí", "Distrito": "Guápiles"},
        {"Provincia": "Limón", "Canton": "Talamanca", "Distrito": "Bratsi"},
        {"Provincia": "Limón", "Canton": "Siquirres", "Distrito": "Siquirres"},
        {"Provincia": "Limón", "Canton": "Matina", "Distrito": "Matina"},
        {"Provincia": "Limón", "Canton": "Guácimo", "Distrito": "Guácimo"}
    ]

    data_final = []
    fecha_inicio = datetime.now() - timedelta(days=25*365)
    fechas = pd.date_range(start=fecha_inicio, end=datetime.now(), freq='MS')

    print(f"Generando aproximadamente {len(fechas) * len(productos_base) * len(ubicaciones)} registros...")

    for fecha in fechas:
        año = fecha.year
        for p in productos_base:
            # Manejo de la inconsistencia en tu llave 'frijoles' vs 'nombre' del producto 15
            nombre_prod = p.get('nombre') if p.get('nombre') else p.get('frijoles')
            # El FactorCanasta se busca en nuestro dict; si no existe, por defecto es 1.0
            factor = dict_factores.get(p['categoria'], 1.0)
            # El PrecioBaseReferencia es el valor estático del diccionario original
            precio_ref = p['precio_base']

            for loc in ubicaciones:
                # Precio base ajustado por producto
                precio = p['precio_base']
                
                # Simulación de tendencia histórica CR
                if año == 2021: precio *= 1.05
                elif año == 2022: precio *= 1.15  # Pico de inflación post-pandemia
                elif año == 2023: precio *= 1.08
                elif año >= 2024: precio *= 0.97  # Tendencia a la baja reciente en CR
                
                # Variación aleatoria por ubicación (ruido de mercado)
                variacion_loc = random.uniform(0.95, 1.05)
                precio_final = round(precio * variacion_loc + random.uniform(-10, 10), 2)

                data_final.append({
                    "Fecha": fecha.strftime('%Y-%m-%d'),
                    "ProductoID": p['id'],
                    "NombreProducto": nombre_prod,
                    "Categoria": p['categoria'],
                    "EsImportado": 1 if p['importado'] else 0,
                    "UnidadMedida": p['unidad'],
                    "Provincia": loc["Provincia"],
                    "Canton": loc["Canton"],
                    "Distrito": loc["Distrito"],
                    "PrecioColones": precio_final,
                    "PrecioBaseReferencia" : precio_final,
                    "FactorCanasta" :  variacion_loc
                })

    # Crear carpeta si no existe
    os.makedirs('data/raw', exist_ok=True)
    
    df = pd.DataFrame(data_final)
    path = "data/raw/historico_canasta_cr.csv"
    df.to_csv(path, index=False, encoding='utf-8-sig')
    print(f"Archivo generado exitosamente en: {path}")

if __name__ == "__main__":
    generar_dataset_canasta()