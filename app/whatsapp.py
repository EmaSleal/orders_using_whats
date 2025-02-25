import requests
from app.config import Config

def enviar_mensaje_whatsapp(to, mensaje):
    """
    Envía un mensaje de WhatsApp utilizando la API de Meta.
    """
    try:
        url = f"https://graph.facebook.com/v21.0/{Config.WHATSAPP_PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {Config.WHATSAPP_API_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": mensaje}
        }
        
        response = requests.post(url, headers=headers, json=payload)
        # print(response.json())
        return response.json()
    except Exception as e:
        # print(f"Error enviando mensaje: {e}")
        return {"error": str(e)}