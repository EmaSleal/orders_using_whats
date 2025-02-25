import os
from dotenv import load_dotenv

load_dotenv()  # Cargar las variables del .env manualmente

class Config:
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    SECRET_KEY = os.getenv("SECRET_KEY", "mi_secreto")

    # Base de Datos
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "Chismosear01")
    DB_NAME = os.getenv("DB_NAME", "facturas_monrachem")

    # WhatsApp API
    WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

    # Puerto de la aplicación
    FLASK_RUN_PORT = int(os.getenv("FLASK_RUN_PORT", 80))  # Cambiar 5000 a 80 como default

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
