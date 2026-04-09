import pyodbc
from src.config import DB_CONFIG


def get_connection():
    """
    Crea y retorna una conexión a SQL Server usando la configuración centralizada.
    """
    try:
        conn = pyodbc.connect(
            f"DRIVER={{{DB_CONFIG['driver']}}};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"UID={DB_CONFIG['username']};"
            f"PWD={DB_CONFIG['password']}"
        )
        return conn

    except Exception as e:
        print("❌ Error al conectar a la base de datos:", e)
        return None