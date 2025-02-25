from flask import Flask
from app.config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Importar rutas
    from app.routes import webhook_bp
    app.register_blueprint(webhook_bp)

    return app
