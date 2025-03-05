from flask import Blueprint, request, jsonify
import requests
import os
import threading
from app.services import procesar_pedido, procesar_reporte, insertar_articulos_desde_excel
from app.database import ejecutar_sp
import json

webhook_bp = Blueprint('webhook', __name__)

BASE_DIR = "C:\\temp" if os.name == "nt" else "/mnt/data"
os.makedirs(BASE_DIR, exist_ok=True)

@webhook_bp.route('/webhook', methods=['POST'])
def webhook():
    """
    Endpoint principal para recibir mensajes de WhatsApp y procesarlos según su tipo.
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "No se recibió información"}), 400

    # 📌 Responder `200 OK` Inmediatamente para evitar reenvíos
    threading.Thread(target=procesar_mensaje, args=(data,)).start()
    return jsonify({"status": "success"}), 200  # ✅ RESPUESTA RÁPIDA


def procesar_mensaje(data):
    """
    Procesa el mensaje de WhatsApp en un hilo separado para evitar retrasos en la respuesta.
    """
    try:
        # 📌 Validar estructura antes de acceder a los índices
        entry = data.get("entry", [])
        if not entry:
            print("⚠️ Error: 'entry' no encontrado en el JSON")
            return

        changes = entry[0].get("changes", [])
        if not changes:
            print("⚠️ Error: 'changes' no encontrado en el JSON")
            return

        value = changes[0].get("value", {})
        contacts = value.get("contacts", [])
        messages = value.get("messages", [])

        if not contacts or not messages:
            print("⚠️ Error: 'contacts' o 'messages' no encontrados en el JSON")
            return

        phone_number = contacts[0].get("wa_id", "Desconocido")
        message_type = messages[0].get("type", "")
        message_id = messages[0].get("id", "")

        if message_type == "text":
            message_body = messages[0].get("text", {}).get("body", "").strip()
        elif message_type == "document":
            message_body = messages[0]["document"].get("caption", "").strip()
        else:
            return  # 🚀 No procesamos si no es texto ni documento
        
        # 📌 Convertir `data` a un string JSON válido
        data_json = json.dumps(data)  # Convierte `data` a un string JSON antes de enviarlo a MySQL

        # 📌 Llamar al procedimiento almacenado para verificar si el mensaje ya se procesó
        existe = 0
        
        resultados = ejecutar_sp("RegistrarWebhook", (message_id, phone_number, message_body, data_json, existe))

        print(f"ℹ️ Procesando mensaje: {resultados}")

        if resultados and resultados[0][0][0] > 0:
            print(f"🚀 Mensaje con ID {message_id} ya procesado. Ignorando.")
            return  # ✅ Evita el doble procesamiento

        # 📌 Procesar reporte
        if message_body.lower().startswith("reporte:"):
            procesar_reporte(message_body, phone_number)

        # 📌 Procesar pedido
        elif message_body.lower().startswith("pedido:"):
            procesar_pedido(message_body, phone_number)

        # 📌 Procesar carga de artículos desde un archivo Excel
        elif message_body.lower().startswith("agregar articulo"):
            if message_type != "document":
                return

            document_id = messages[0]["document"]["id"]
            filename = messages[0]["document"]["filename"]
            mime_type = messages[0]["document"]["mime_type"]

            if mime_type not in [
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel"
            ]:
                return

            file_url = obtener_url_documento(document_id)
            if not file_url:
                return

            file_path = os.path.join(BASE_DIR, filename)

            response = requests.get(file_url, headers={"Authorization": f"Bearer {os.getenv('WHATSAPP_API_TOKEN')}"})

            if response.status_code == 200:
                with open(file_path, "wb") as file:
                    file.write(response.content)

                insertar_articulos_desde_excel(file_path)

    except Exception as e:
        print(f"⚠️ Error procesando mensaje: {e}")


def obtener_url_documento(document_id):
    """
    Llama a la API de WhatsApp para obtener la URL de descarga de un documento.
    """
    try:
        url = f"https://graph.facebook.com/v16.0/{document_id}"
        headers = {"Authorization": f"Bearer {os.getenv('WHATSAPP_API_TOKEN')}"}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.json().get("url")
        return None
    except Exception as e:
        print(f"⚠️ Excepción al obtener la URL del documento: {e}")
        return None
