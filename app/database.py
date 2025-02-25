import mysql.connector
from app.config import Config

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
        return connection
    except mysql.connector.Error as err:
        print(f"Error de conexión a MySQL: {err}")
        return None

def ejecutar_sp(nombre_sp, parametros):
    """
    Ejecuta un procedimiento almacenado en MySQL.
    """
    conexion = get_db_connection()
    if not conexion:
        return None

    try:
        cursor = conexion.cursor()
        cursor.callproc(nombre_sp, parametros)
        
        resultados = []
        for resultado in cursor.stored_results():
            resultados.append(resultado.fetchall())

        conexion.commit()
        cursor.close()
        conexion.close()

        return resultados
    except mysql.connector.Error as err:
        print(f"Error ejecutando {nombre_sp}: {err}")
        return None
