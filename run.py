from app import create_app
from app.config import Config

app = create_app()

if __name__ == "__main__":
    puerto = Config.FLASK_RUN_PORT  # Tomar el puerto de config.py
    print(f"Iniciando Flask en el puerto {puerto}...")  # Para verificar en consola
    app.run(host="0.0.0.0", port=puerto, debug=True)
